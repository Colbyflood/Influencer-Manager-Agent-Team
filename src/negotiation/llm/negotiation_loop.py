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
from negotiation.llm.composer import compose_agreement_email, compose_counter_email
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
    kb_content = load_knowledge_base(
        str(negotiation_context["platform"]),
        stage=str(negotiation_context.get("negotiation_stage", "")),
    )

    # Step 3 - Classify intent
    classification = classify_intent(email_body, str(negotiation_context), client)

    # Step 4 - Handle UNCLEAR intent
    if classification.intent == NegotiationIntent.UNCLEAR:
        return {
            "action": "escalate",
            "reason": f"Low confidence intent: {classification.confidence}",
            "classification": classification,
        }

    # Step 5 - Handle ACCEPT -- compose agreement confirmation email
    if classification.intent == NegotiationIntent.ACCEPT:
        state_machine.trigger("accept")

        # Load knowledge base with stage="agreed"
        kb_content_agreed = load_knowledge_base(
            str(negotiation_context["platform"]),
            stage="agreed",
        )

        # Get counterparty tone guidance
        from negotiation.counterparty.tone import get_tone_guidance as _get_tone_accept

        counterparty_type_accept = str(
            negotiation_context.get("counterparty_type", "direct_influencer")
        )
        agency_name_accept = negotiation_context.get("agency_name")
        tone_guidance_accept = _get_tone_accept(counterparty_type_accept, agency_name_accept)

        # Determine agreed rate
        agreed_rate = str(
            negotiation_context.get(
                "last_offered_rate",
                str(
                    calculate_rate(
                        int(negotiation_context["average_views"]),
                        Decimal(str(negotiation_context["next_cpm"])),
                    )
                ),
            )
        )

        # Compose agreement confirmation email
        composed_agreement = compose_agreement_email(
            influencer_name=str(negotiation_context["influencer_name"]),
            agreed_rate=agreed_rate,
            deliverables_summary=str(negotiation_context["deliverables_summary"]),
            usage_rights_summary=negotiation_context.get("usage_rights_summary"),
            platform=str(negotiation_context["platform"]),
            payment_terms=str(
                negotiation_context.get("payment_terms", "within 30 days of content going live")
            ),
            knowledge_base_content=kb_content_agreed,
            negotiation_history=str(negotiation_context.get("history", "")),
            client=client,
            counterparty_context=tone_guidance_accept,
        )

        # Validate the agreement email
        agreement_validation = validate_composed_email(
            email_body=composed_agreement.email_body,
            expected_rate=Decimal(agreed_rate),
            expected_deliverables=list(negotiation_context["deliverable_types"]),
            influencer_name=str(negotiation_context["influencer_name"]),
            is_agreement=True,
        )

        if agreement_validation.passed:
            return {
                "action": "accept",
                "classification": classification,
                "email_body": composed_agreement.email_body,
            }
        # Accept anyway but flag warnings for human review
        return {
            "action": "accept",
            "classification": classification,
            "email_body": composed_agreement.email_body,
            "validation_warnings": agreement_validation.failures,
        }

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

    # Step 8 - Calculate base rate and select negotiation lever
    next_cpm = Decimal(str(negotiation_context["next_cpm"]))
    our_base_rate = calculate_rate(average_views, next_cpm)

    # Step 8.5 - Select negotiation lever
    from negotiation.levers import select_lever
    from negotiation.levers.models import NegotiationLeverContext

    lever_ctx = NegotiationLeverContext(
        their_rate=(
            Decimal(classification.proposed_rate) if classification.proposed_rate else our_base_rate
        ),
        our_current_rate=our_base_rate,
        average_views=average_views,
        current_scenario=int(negotiation_context.get("current_scenario", 1)),
        current_usage_tier=str(negotiation_context.get("current_usage_tier", "target")),
        product_offered=bool(negotiation_context.get("product_offered", False)),
        syndication_proposed=bool(negotiation_context.get("syndication_proposed", False)),
        cpm_shared=bool(negotiation_context.get("cpm_shared", False)),
        round_number=round_count,
        deliverable_scenarios=negotiation_context.get("deliverable_scenarios"),
        usage_rights=negotiation_context.get("usage_rights"),
        budget_constraints=negotiation_context.get("budget_constraints"),
        product_leverage=negotiation_context.get("product_leverage"),
    )

    lever_result = select_lever(lever_ctx)

    # Handle escalation from lever engine (NEG-12 ceiling)
    if lever_result.should_escalate:
        state_machine.trigger("escalate")
        return {
            "action": "escalate",
            "reason": f"Lever engine: {lever_result.action.value}",
            "lever": lever_result,
            "classification": classification,
        }

    # Handle graceful exit from lever engine (NEG-15)
    if lever_result.should_exit:
        state_machine.trigger("reject")
        return {
            "action": "exit",
            "reason": "All negotiation levers exhausted",
            "lever": lever_result,
            "classification": classification,
        }

    # Use lever-adjusted rate and deliverables
    our_rate = (
        lever_result.adjusted_rate if lever_result.adjusted_rate is not None else our_base_rate
    )
    deliverables_for_email = lever_result.deliverables_summary or str(
        negotiation_context["deliverables_summary"]
    )

    # Step 8.7 - Generate counterparty tone guidance
    from negotiation.counterparty.tone import get_tone_guidance

    counterparty_type = str(negotiation_context.get("counterparty_type", "direct_influencer"))
    agency_name = negotiation_context.get("agency_name")
    tone_guidance = get_tone_guidance(counterparty_type, agency_name)

    # Step 9 - Compose counter-offer email
    negotiation_stage = (
        "counter" if classification.intent == NegotiationIntent.COUNTER else "question_response"
    )
    composed = compose_counter_email(
        influencer_name=str(negotiation_context["influencer_name"]),
        their_rate=classification.proposed_rate or "not specified",
        our_rate=str(our_rate),
        deliverables_summary=deliverables_for_email,
        platform=str(negotiation_context["platform"]),
        negotiation_stage=negotiation_stage,
        knowledge_base_content=kb_content,
        negotiation_history=str(negotiation_context.get("history", "")),
        client=client,
        lever_instructions=lever_result.lever_instructions,
        counterparty_context=tone_guidance,
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
        "lever": lever_result,
    }
