"""End-to-end negotiation loop orchestrator.

Wires together intent classification, the pricing engine, email composition,
the validation gate, and the state machine into a single
``process_influencer_reply`` function that decides the correct action for
each influencer reply.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from anthropic import Anthropic

from negotiation.llm.client import DEFAULT_MAX_ROUNDS
from negotiation.llm.composer import compose_counter_email
from negotiation.llm.intent import classify_intent
from negotiation.llm.knowledge_base import load_knowledge_base
from negotiation.llm.models import EscalationPayload, NegotiationIntent
from negotiation.llm.validation import validate_composed_email
from negotiation.pricing import calculate_rate, evaluate_proposed_rate
from negotiation.state_machine import NegotiationStateMachine


def process_influencer_reply(
    email_body: str,
    negotiation_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
    client: Anthropic,
    round_count: int,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> dict[str, Any]:
    """Orchestrate the full negotiation loop for a single influencer reply.

    Coordinates intent classification, pricing evaluation, email composition,
    and validation into a single decision function.  Returns an action dict
    indicating whether to send, escalate, accept, or reject.

    Args:
        email_body: The raw text of the influencer's email reply.
        negotiation_context: Must contain keys: ``influencer_name`` (str),
            ``thread_id`` (str), ``platform`` (str), ``average_views`` (int),
            ``deliverables_summary`` (str), ``deliverable_types`` (list[str]),
            ``next_cpm`` (Decimal), ``history`` (str, optional).
        state_machine: Current negotiation state machine instance.
        client: Configured Anthropic client.
        round_count: Current round number (0-based).
        max_rounds: Maximum autonomous rounds before escalation.

    Returns:
        A dict with ``"action"`` key (one of ``"send"``, ``"escalate"``,
        ``"accept"``, ``"reject"``) and action-specific data.
    """
    # Step 1 - Check round cap
    if round_count >= max_rounds:
        return {
            "action": "escalate",
            "reason": f"Max autonomous rounds ({max_rounds}) reached",
            "payload": EscalationPayload(
                reason=f"Max autonomous rounds ({max_rounds}) reached",
                email_draft="",
                validation_failures=[],
                influencer_name=str(negotiation_context["influencer_name"]),
                thread_id=str(negotiation_context["thread_id"]),
            ),
        }

    # Step 2 - Load knowledge base
    kb_content = load_knowledge_base(str(negotiation_context["platform"]))

    # Step 3 - Classify intent
    classification = classify_intent(email_body, str(negotiation_context), client)

    # Step 4 - Handle UNCLEAR intent
    if classification.intent == NegotiationIntent.UNCLEAR:
        return {
            "action": "escalate",
            "reason": f"Low confidence intent: {classification.confidence}",
            "classification": classification,
        }

    # Step 5 - Handle ACCEPT
    if classification.intent == NegotiationIntent.ACCEPT:
        state_machine.trigger("accept")
        return {"action": "accept", "classification": classification}

    # Step 6 - Handle REJECT
    if classification.intent == NegotiationIntent.REJECT:
        state_machine.trigger("reject")
        return {"action": "reject", "classification": classification}

    # Step 7 - Handle COUNTER or QUESTION -- calculate pricing
    state_machine.trigger("receive_reply")

    average_views: int = int(negotiation_context["average_views"])

    if classification.proposed_rate is not None:
        proposed = Decimal(classification.proposed_rate)
        pricing = evaluate_proposed_rate(
            proposed_rate=proposed,
            average_views=average_views,
        )
        if pricing.should_escalate:
            state_machine.trigger("escalate")
            return {
                "action": "escalate",
                "reason": pricing.warning,
                "pricing": pricing,
                "classification": classification,
            }

    # Step 8 - Calculate our counter rate
    next_cpm = Decimal(str(negotiation_context["next_cpm"]))
    our_rate = calculate_rate(average_views, next_cpm)

    # Step 9 - Compose counter-offer email
    negotiation_stage = (
        "counter" if classification.intent == NegotiationIntent.COUNTER else "question_response"
    )
    composed = compose_counter_email(
        influencer_name=str(negotiation_context["influencer_name"]),
        their_rate=classification.proposed_rate or "not specified",
        our_rate=str(our_rate),
        deliverables_summary=str(negotiation_context["deliverables_summary"]),
        platform=str(negotiation_context["platform"]),
        negotiation_stage=negotiation_stage,
        knowledge_base_content=kb_content,
        negotiation_history=str(negotiation_context.get("history", "")),
        client=client,
    )

    # Step 10 - Validate before sending
    deliverable_types: list[str] = list(negotiation_context["deliverable_types"])
    validation = validate_composed_email(
        email_body=composed.email_body,
        expected_rate=our_rate,
        expected_deliverables=deliverable_types,
        influencer_name=str(negotiation_context["influencer_name"]),
    )

    if not validation.passed:
        return {
            "action": "escalate",
            "reason": "Validation failed",
            "payload": EscalationPayload(
                reason="Email validation failed",
                email_draft=composed.email_body,
                validation_failures=validation.failures,
                influencer_name=str(negotiation_context["influencer_name"]),
                thread_id=str(negotiation_context["thread_id"]),
                our_rate=our_rate,
            ),
        }

    # Step 11 - Email validated, trigger send
    state_machine.trigger("send_counter")
    return {
        "action": "send",
        "email_body": composed.email_body,
        "our_rate": our_rate,
        "round": round_count + 1,
        "classification": classification,
    }
