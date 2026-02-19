"""Integration tests for the end-to-end negotiation loop.

Tests use real pricing engine and state machine but mock LLM calls (both
intent classification via messages.parse and email composition via messages.create).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from negotiation.domain.types import NegotiationState
from negotiation.llm.models import (
    IntentClassification,
    NegotiationIntent,
)
from negotiation.llm.negotiation_loop import process_influencer_reply
from negotiation.state_machine import NegotiationStateMachine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a MagicMock standing in for anthropic.Anthropic."""
    return MagicMock()


@pytest.fixture()
def base_context() -> dict[str, Any]:
    """Standard negotiation context dict."""
    return {
        "influencer_name": "Jane Creator",
        "platform": "instagram",
        "average_views": 100_000,
        "deliverables_summary": "1 Instagram Reel",
        "deliverable_types": ["instagram_reel"],
        "thread_id": "thread_123",
        "next_cpm": Decimal("25"),
    }


@pytest.fixture()
def state_machine() -> NegotiationStateMachine:
    """State machine at AWAITING_REPLY (after initial send_offer)."""
    sm = NegotiationStateMachine()
    sm.trigger("send_offer")
    assert sm.state == NegotiationState.AWAITING_REPLY
    return sm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parse_response(classification: IntentClassification) -> MagicMock:
    """Wrap an IntentClassification in a mock ParsedMessage-like object."""
    response = MagicMock()
    response.parsed_output = classification
    return response


def _make_compose_response(email_text: str) -> MagicMock:
    """Create a mock messages.create response with given email body."""
    mock_response = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = email_text
    mock_response.content = [mock_content_block]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 400
    mock_response.usage.output_tokens = 150
    return mock_response


def _configure_mock_client(
    mock_client: MagicMock,
    classification: IntentClassification,
    compose_text: str = "",
) -> None:
    """Configure mock client for both classify (parse) and compose (create)."""
    mock_client.messages.parse.return_value = _make_parse_response(classification)
    if compose_text:
        mock_client.messages.create.return_value = _make_compose_response(compose_text)


# ---------------------------------------------------------------------------
# Test: Max rounds escalation
# ---------------------------------------------------------------------------


def test_max_rounds_escalation(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """When round_count >= max_rounds, escalate immediately without LLM calls."""
    result = process_influencer_reply(
        email_body="I'd like to counter at $3,000.",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=5,
        max_rounds=5,
    )

    assert result["action"] == "escalate"
    assert "Max autonomous rounds" in str(result["reason"])
    # State machine unchanged -- no trigger called
    assert state_machine.state == NegotiationState.AWAITING_REPLY
    # No LLM calls should have been made
    mock_client.messages.parse.assert_not_called()
    mock_client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Unclear intent escalation
# ---------------------------------------------------------------------------


def test_unclear_intent_escalation(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """When intent is UNCLEAR, escalate with low-confidence reason."""
    classification = IntentClassification(
        intent=NegotiationIntent.UNCLEAR,
        confidence=0.3,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Cannot determine intent.",
        key_concerns=[],
    )
    _configure_mock_client(mock_client, classification)

    result = process_influencer_reply(
        email_body="Hmm, interesting...",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=0,
    )

    assert result["action"] == "escalate"
    assert "Low confidence" in str(result["reason"])
    assert result["classification"] == classification


# ---------------------------------------------------------------------------
# Test: Accept transitions to AGREED
# ---------------------------------------------------------------------------


def test_accept_transitions_to_agreed(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """ACCEPT intent triggers accept on state machine -> AGREED terminal state."""
    # State machine must be in COUNTER_RECEIVED for accept to work.
    # advance: AWAITING_REPLY -> COUNTER_RECEIVED
    state_machine.trigger("receive_reply")
    assert state_machine.state == NegotiationState.COUNTER_RECEIVED

    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.95,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Influencer agrees to the deal.",
        key_concerns=[],
    )
    _configure_mock_client(mock_client, classification)

    result = process_influencer_reply(
        email_body="Sounds great, let's do it!",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=1,
    )

    assert result["action"] == "accept"
    assert result["classification"] == classification
    assert state_machine.state == NegotiationState.AGREED
    assert state_machine.is_terminal


# ---------------------------------------------------------------------------
# Test: Reject transitions to REJECTED
# ---------------------------------------------------------------------------


def test_reject_transitions_to_rejected(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """REJECT intent triggers reject on state machine -> REJECTED terminal state."""
    # advance: AWAITING_REPLY -> COUNTER_RECEIVED
    state_machine.trigger("receive_reply")
    assert state_machine.state == NegotiationState.COUNTER_RECEIVED

    classification = IntentClassification(
        intent=NegotiationIntent.REJECT,
        confidence=0.90,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Influencer declines the partnership.",
        key_concerns=[],
    )
    _configure_mock_client(mock_client, classification)

    result = process_influencer_reply(
        email_body="I'll pass, thanks.",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=1,
    )

    assert result["action"] == "reject"
    assert result["classification"] == classification
    assert state_machine.state == NegotiationState.REJECTED
    assert state_machine.is_terminal


# ---------------------------------------------------------------------------
# Test: Counter within range sends email
# ---------------------------------------------------------------------------


def test_counter_within_range_sends_email(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """COUNTER with rate within CPM range -> compose, validate, send."""
    classification = IntentClassification(
        intent=NegotiationIntent.COUNTER,
        confidence=0.92,
        proposed_rate="1500.00",
        proposed_deliverables=[],
        summary="Influencer counters with $1,500.",
        key_concerns=[],
    )
    # our_rate = calculate_rate(100_000, Decimal("25")) = 100 * 25 = $2,500.00
    # The composed email must contain exactly $2,500.00 to pass validation
    email_text = (
        "Hi Jane Creator,\n\n"
        "Thank you for your proposal. We'd like to offer $2500.00 "
        "for 1 Instagram Reel. Let us know!\n\nBest regards"
    )
    _configure_mock_client(mock_client, classification, compose_text=email_text)

    result = process_influencer_reply(
        email_body="I'd accept for $1,500.",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=0,
    )

    assert result["action"] == "send"
    assert "email_body" in result
    assert result["our_rate"] == Decimal("2500.00")
    assert result["round"] == 1
    assert state_machine.state == NegotiationState.COUNTER_SENT


# ---------------------------------------------------------------------------
# Test: Counter exceeds CPM ceiling -> escalate
# ---------------------------------------------------------------------------


def test_counter_exceeds_ceiling_escalates(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """COUNTER with proposed rate above CPM ceiling -> escalate with pricing context."""
    # proposed_rate="50000.00" with 100k views -> CPM = 50000 / 100 = $500 >> $30 ceiling
    classification = IntentClassification(
        intent=NegotiationIntent.COUNTER,
        confidence=0.92,
        proposed_rate="50000.00",
        proposed_deliverables=[],
        summary="Influencer counters with $50,000.",
        key_concerns=[],
    )
    _configure_mock_client(mock_client, classification)

    result = process_influencer_reply(
        email_body="My rate is $50,000 for this.",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=0,
    )

    assert result["action"] == "escalate"
    assert "CPM" in str(result.get("reason", "")) or "ceiling" in str(result.get("reason", ""))
    assert "pricing" in result
    assert "classification" in result
    assert state_machine.state == NegotiationState.ESCALATED


# ---------------------------------------------------------------------------
# Test: Validation failure escalates with payload
# ---------------------------------------------------------------------------


def test_validation_failure_escalates(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """When composed email fails validation (wrong amount), escalate with draft."""
    classification = IntentClassification(
        intent=NegotiationIntent.COUNTER,
        confidence=0.92,
        proposed_rate="1500.00",
        proposed_deliverables=[],
        summary="Influencer counters with $1,500.",
        key_concerns=[],
    )
    # Compose returns email with WRONG amount ($999.00 instead of $2,500.00)
    email_text = (
        "Hi Jane Creator,\n\n"
        "We'd like to offer $999.00 for 1 Instagram Reel. "
        "Let us know what you think!\n\nBest regards"
    )
    _configure_mock_client(mock_client, classification, compose_text=email_text)

    result = process_influencer_reply(
        email_body="I'd accept for $1,500.",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=0,
    )

    assert result["action"] == "escalate"
    assert result["reason"] == "Validation failed"
    payload = result["payload"]
    assert payload.reason == "Email validation failed"
    assert len(payload.validation_failures) > 0
    assert payload.email_draft == email_text
    assert payload.our_rate == Decimal("2500.00")


# ---------------------------------------------------------------------------
# Test: Question intent composes response
# ---------------------------------------------------------------------------


def test_question_intent_composes_response(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """QUESTION intent triggers compose with stage='question_response' and sends."""
    classification = IntentClassification(
        intent=NegotiationIntent.QUESTION,
        confidence=0.85,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Influencer asks about timeline.",
        key_concerns=["What's the timeline?"],
    )
    email_text = (
        "Hi Jane Creator,\n\n"
        "Great question! Our budget for this reel is $2500.00. "
        "The timeline is flexible.\n\nBest regards"
    )
    _configure_mock_client(mock_client, classification, compose_text=email_text)

    result = process_influencer_reply(
        email_body="What's the timeline for this project?",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=0,
    )

    assert result["action"] == "send"
    # Verify negotiation_stage was "question_response" in the compose call
    compose_call_kwargs = mock_client.messages.create.call_args.kwargs
    user_content = compose_call_kwargs["messages"][0]["content"]
    assert "question_response" in user_content
    assert state_machine.state == NegotiationState.COUNTER_SENT


# ---------------------------------------------------------------------------
# Test: Low confidence counter overridden to UNCLEAR -> escalate
# ---------------------------------------------------------------------------


def test_low_confidence_counter_overridden_to_unclear(
    mock_client: MagicMock,
    base_context: dict[str, Any],
    state_machine: NegotiationStateMachine,
) -> None:
    """COUNTER with confidence 0.4 is overridden to UNCLEAR by classify_intent."""
    # classify_intent will override COUNTER -> UNCLEAR when confidence < 0.70
    classification = IntentClassification(
        intent=NegotiationIntent.COUNTER,
        confidence=0.4,
        proposed_rate="1500.00",
        proposed_deliverables=[],
        summary="Ambiguous counter.",
        key_concerns=[],
    )
    # After classify_intent processes this, intent will be UNCLEAR
    # because 0.4 < 0.70 threshold
    _configure_mock_client(mock_client, classification)

    result = process_influencer_reply(
        email_body="Maybe something around $1,500...",
        negotiation_context=base_context,
        state_machine=state_machine,
        client=mock_client,
        round_count=0,
    )

    assert result["action"] == "escalate"
    assert "Low confidence" in str(result["reason"])
    # The returned classification should have intent UNCLEAR (overridden)
    returned_classification = result["classification"]
    assert returned_classification.intent == NegotiationIntent.UNCLEAR
