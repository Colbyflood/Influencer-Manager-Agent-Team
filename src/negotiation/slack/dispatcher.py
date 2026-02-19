"""Unified dispatch layer integrating triggers, human takeover, and Slack notifications.

The SlackDispatcher sits between the negotiation loop and Slack, handling
pre-processing (trigger evaluation, human takeover check) and post-processing
(escalation/agreement dispatch with full Block Kit messages).

Pre-check runs BEFORE ``process_influencer_reply``; handle_negotiation_result
runs AFTER to convert action dicts into Slack messages.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from negotiation.llm.models import AgreementPayload, EscalationPayload
from negotiation.slack.blocks import build_agreement_blocks, build_escalation_blocks
from negotiation.slack.client import SlackNotifier
from negotiation.slack.takeover import ThreadStateManager, detect_human_reply
from negotiation.slack.triggers import EscalationTriggersConfig, evaluate_triggers

logger = logging.getLogger(__name__)


class SlackDispatcher:
    """Orchestrates trigger evaluation, human takeover check, and Slack dispatch.

    The dispatcher is the integration point for all Phase 4 components:

    1. **pre_check** -- runs before the negotiation loop to catch emails that
       should be escalated or skipped before any autonomous response.
    2. **dispatch_escalation** / **dispatch_agreement** -- convert payloads into
       Block Kit messages and post them to Slack.
    3. **handle_negotiation_result** -- takes the action dict from
       ``process_influencer_reply`` and dispatches to Slack as needed.
    """

    def __init__(
        self,
        notifier: SlackNotifier,
        thread_state_manager: ThreadStateManager,
        triggers_config: EscalationTriggersConfig,
        agent_email: str,
    ) -> None:
        """Initialize the SlackDispatcher.

        Args:
            notifier: SlackNotifier for posting messages to Slack channels.
            thread_state_manager: ThreadStateManager for tracking thread ownership.
            triggers_config: Configuration for escalation triggers.
            agent_email: The email address used by the agent.
        """
        self._notifier = notifier
        self._thread_state = thread_state_manager
        self._triggers_config = triggers_config
        self._agent_email = agent_email

    def pre_check(
        self,
        email_body: str,
        thread_id: str,
        influencer_email: str,
        proposed_cpm: float,
        intent_confidence: float,
        gmail_service: Any,
        anthropic_client: Any | None,
    ) -> dict[str, Any] | None:
        """Run pre-processing gates before the negotiation loop.

        Checks human takeover status, detects human replies in Gmail threads,
        and evaluates escalation triggers. Returns an action dict if processing
        should stop, or ``None`` if the negotiation loop should proceed.

        Args:
            email_body: The influencer's email body text.
            thread_id: The Gmail thread ID.
            influencer_email: The influencer's email address.
            proposed_cpm: The calculated CPM from proposed rate and average views.
            intent_confidence: Confidence score from intent classification.
            gmail_service: An authenticated Gmail API v1 service resource.
            anthropic_client: Anthropic API client (None skips LLM triggers).

        Returns:
            Action dict if processing should stop, ``None`` to proceed.
        """
        # 1. Check if thread is already human-managed (silent skip)
        if self._thread_state.is_human_managed(thread_id):
            logger.info("Thread %s is human-managed, skipping", thread_id)
            return {"action": "skip", "reason": "Thread is human-managed"}

        # 2. Check for human reply in Gmail thread (auto-claim)
        if detect_human_reply(gmail_service, thread_id, self._agent_email, influencer_email):
            self._thread_state.claim_thread(thread_id, "auto-detected")
            logger.info("Human reply detected in thread %s, auto-claimed", thread_id)
            return {"action": "skip", "reason": "Human reply detected in thread"}

        # 3. Evaluate escalation triggers
        fired_triggers = evaluate_triggers(
            email_body,
            proposed_cpm,
            intent_confidence,
            self._triggers_config,
            anthropic_client,
        )
        if fired_triggers:
            first_trigger = fired_triggers[0]
            logger.info(
                "Trigger fired for thread %s: %s",
                thread_id,
                first_trigger.reason,
            )
            return {
                "action": "escalate",
                "triggers": fired_triggers,
                "reason": first_trigger.reason,
            }

        # 4. No gates fired -- proceed with negotiation loop
        return None

    def dispatch_escalation(self, payload: EscalationPayload) -> str:
        """Dispatch an escalation notification to Slack.

        Builds Block Kit blocks from the payload and posts to the escalation
        channel via SlackNotifier.

        Args:
            payload: The escalation data to post.

        Returns:
            The Slack message timestamp (ts) for reference.
        """
        details_link = f"https://mail.google.com/mail/u/0/#inbox/{payload.thread_id}"
        blocks = build_escalation_blocks(
            influencer_name=payload.influencer_name,
            influencer_email=payload.influencer_email,
            client_name=payload.client_name,
            escalation_reason=payload.reason,
            evidence_quote=payload.evidence_quote,
            proposed_rate=str(payload.proposed_rate) if payload.proposed_rate else None,
            our_rate=str(payload.our_rate) if payload.our_rate else None,
            suggested_actions=payload.suggested_actions,
            details_link=details_link,
        )
        fallback_text = f"Escalation: {payload.influencer_name} - {payload.reason}"
        return self._notifier.post_escalation(blocks, fallback_text)

    def dispatch_agreement(self, payload: AgreementPayload) -> str:
        """Dispatch an agreement notification to Slack.

        Builds Block Kit blocks from the payload and posts to the agreement
        channel via SlackNotifier.

        Args:
            payload: The agreement data to post.

        Returns:
            The Slack message timestamp (ts) for reference.
        """
        blocks = build_agreement_blocks(
            influencer_name=payload.influencer_name,
            influencer_email=payload.influencer_email,
            client_name=payload.client_name,
            agreed_rate=payload.agreed_rate,
            platform=payload.platform,
            deliverables=payload.deliverables,
            cpm_achieved=payload.cpm_achieved,
            next_steps=payload.next_steps,
            mention_users=payload.mention_users if payload.mention_users else None,
        )
        fallback_text = f"Deal Agreed: {payload.influencer_name} - ${payload.agreed_rate:,.2f}"
        return self._notifier.post_agreement(blocks, fallback_text)

    def handle_negotiation_result(
        self,
        result: dict[str, Any],
        negotiation_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Route negotiation results to Slack dispatch as needed.

        Takes the action dict from ``process_influencer_reply`` and dispatches
        escalation or agreement notifications to Slack. Non-dispatch actions
        (``send``, ``reject``) pass through unchanged.

        Args:
            result: The action dict from the negotiation loop. Must have
                ``"action"`` key with value ``"escalate"``, ``"accept"``,
                ``"send"``, or ``"reject"``.
            negotiation_context: Negotiation context dict with keys like
                ``influencer_name``, ``influencer_email``, ``client_name``,
                ``thread_id``, ``platform``, ``average_views``, etc.

        Returns:
            The (potentially enriched) result dict with ``"slack_ts"`` added
            for escalation and agreement actions.
        """
        action = result.get("action", "")

        if action == "escalate":
            esc_payload = self._build_escalation_payload(result, negotiation_context)
            slack_ts = self.dispatch_escalation(esc_payload)
            result["slack_ts"] = slack_ts

        elif action == "accept":
            agr_payload = self._build_agreement_payload(result, negotiation_context)
            slack_ts = self.dispatch_agreement(agr_payload)
            result["slack_ts"] = slack_ts

        return result

    def _build_escalation_payload(
        self,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> EscalationPayload:
        """Build EscalationPayload from negotiation result and context.

        Populates Phase 4 fields: influencer_email, client_name, evidence_quote,
        suggested_actions, trigger_type.

        Args:
            result: The escalation action dict from the negotiation loop.
            context: The negotiation context dict.

        Returns:
            A fully populated EscalationPayload.
        """
        # Extract trigger info if available
        triggers = result.get("triggers", [])
        trigger_type = ""
        evidence_quote = ""
        if triggers:
            first_trigger = triggers[0]
            if hasattr(first_trigger, "trigger_type"):
                trigger_type = str(first_trigger.trigger_type)
            else:
                trigger_type = str(first_trigger.get("trigger_type", ""))
            if hasattr(first_trigger, "evidence"):
                evidence_quote = first_trigger.evidence
            else:
                evidence_quote = first_trigger.get("evidence", "")

        # Build suggested actions based on escalation reason
        reason = result.get("reason", "")
        suggested_actions = self._suggest_actions(reason, result)

        # Get existing payload if present (from negotiation loop)
        existing_payload = result.get("payload")

        if isinstance(existing_payload, EscalationPayload):
            # Enrich existing payload with Phase 4 fields
            return EscalationPayload(
                reason=existing_payload.reason,
                email_draft=existing_payload.email_draft,
                validation_failures=existing_payload.validation_failures,
                influencer_name=existing_payload.influencer_name,
                thread_id=existing_payload.thread_id,
                proposed_rate=existing_payload.proposed_rate,
                our_rate=existing_payload.our_rate,
                influencer_email=context.get("influencer_email", ""),
                client_name=context.get("client_name", ""),
                evidence_quote=evidence_quote,
                suggested_actions=suggested_actions,
                trigger_type=trigger_type,
            )

        # Build new payload from scratch
        classification = result.get("classification")
        proposed_rate: Decimal | None = None
        if (
            classification
            and hasattr(classification, "proposed_rate")
            and classification.proposed_rate
        ):
            proposed_rate = Decimal(classification.proposed_rate)

        return EscalationPayload(
            reason=reason,
            email_draft="",
            influencer_name=context.get("influencer_name", ""),
            thread_id=context.get("thread_id", ""),
            proposed_rate=proposed_rate,
            our_rate=context.get("our_rate"),
            influencer_email=context.get("influencer_email", ""),
            client_name=context.get("client_name", ""),
            evidence_quote=evidence_quote,
            suggested_actions=suggested_actions,
            trigger_type=trigger_type,
        )

    def _build_agreement_payload(
        self,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> AgreementPayload:
        """Build AgreementPayload from negotiation result and context.

        Populates: agreed_rate, platform, deliverables, cpm_achieved,
        next_steps, mention_users.

        Args:
            result: The accept action dict from the negotiation loop.
            context: The negotiation context dict.

        Returns:
            A fully populated AgreementPayload.
        """
        classification = result.get("classification")
        agreed_rate = Decimal("0")
        if (
            classification
            and hasattr(classification, "proposed_rate")
            and classification.proposed_rate
        ):
            agreed_rate = Decimal(classification.proposed_rate)
        elif context.get("agreed_rate"):
            agreed_rate = Decimal(str(context["agreed_rate"]))

        average_views = int(context.get("average_views", 1))
        cpm_achieved = (
            agreed_rate / Decimal(str(average_views)) * Decimal("1000")
            if average_views > 0
            else Decimal("0")
        )

        return AgreementPayload(
            influencer_name=context.get("influencer_name", ""),
            influencer_email=context.get("influencer_email", ""),
            client_name=context.get("client_name", ""),
            agreed_rate=agreed_rate,
            platform=context.get("platform", ""),
            deliverables=context.get("deliverables_summary", ""),
            cpm_achieved=cpm_achieved,
            thread_id=context.get("thread_id", ""),
            next_steps=context.get(
                "next_steps",
                [
                    "Send contract",
                    "Confirm deliverables",
                    "Schedule content calendar",
                ],
            ),
            mention_users=context.get("mention_users", []),
        )

    @staticmethod
    def _suggest_actions(reason: str, result: dict[str, Any]) -> list[str]:
        """Generate suggested actions based on escalation reason.

        Args:
            reason: The escalation reason string.
            result: The full result dict for additional context.

        Returns:
            List of suggested action strings.
        """
        if "cpm" in reason.lower() or "threshold" in reason.lower():
            return [
                "Reply with counter at a lower rate",
                "Approve the proposed rate",
            ]

        if "confidence" in reason.lower() or "intent" in reason.lower():
            return [
                "Review the email and clarify intent",
                "Reply manually with specific questions",
            ]

        if "hostile" in reason.lower() or "tone" in reason.lower():
            return [
                "Review the conversation tone",
                "Reply with a conciliatory message",
                "Escalate to account manager",
            ]

        if "legal" in reason.lower() or "contract" in reason.lower():
            return [
                "Forward to legal team for review",
                "Reply acknowledging legal concerns",
            ]

        if "validation" in reason.lower():
            return [
                "Review the draft email",
                "Edit and send manually",
            ]

        if "round" in reason.lower() or "max" in reason.lower():
            return [
                "Review negotiation history",
                "Make a final offer",
                "Accept current terms",
            ]

        return [
            "Review the conversation",
            "Reply manually",
        ]
