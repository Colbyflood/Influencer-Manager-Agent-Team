"""Tests for intent classification using mocked Anthropic API.

All tests use mocked Anthropic client -- no real API calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from negotiation.llm.client import DEFAULT_CONFIDENCE_THRESHOLD, INTENT_MODEL
from negotiation.llm.intent import classify_intent
from negotiation.llm.models import (
    IntentClassification,
    NegotiationIntent,
    ProposedDeliverable,
)
from negotiation.llm.prompts import INTENT_CLASSIFICATION_SYSTEM_PROMPT


@pytest.fixture()
def mock_anthropic_client() -> MagicMock:
    """Return a MagicMock standing in for anthropic.Anthropic."""
    return MagicMock()


def make_mock_parse_response(
    classification: IntentClassification,
) -> MagicMock:
    """Wrap an IntentClassification in a mock ParsedMessage-like object."""
    response = MagicMock()
    response.parsed_output = classification
    return response


# --- Test ACCEPT intent ---


def test_classify_accept_intent(mock_anthropic_client: MagicMock) -> None:
    """Clear acceptance email returns ACCEPT with high confidence."""
    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.95,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Influencer agrees to the deal.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="Sounds great, let's do it!",
        negotiation_context="Initial offer of $1,000 for 1 Instagram reel.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.ACCEPT
    assert result.confidence >= 0.8
    assert result.proposed_rate is None


# --- Test COUNTER intent with rate ---


def test_classify_counter_with_rate(mock_anthropic_client: MagicMock) -> None:
    """Counter-offer with rate extracts proposed_rate as string dollar amount."""
    classification = IntentClassification(
        intent=NegotiationIntent.COUNTER,
        confidence=0.92,
        proposed_rate="2000.00",
        proposed_deliverables=[],
        summary="Influencer counters with $2,000.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="I'd love to but I charge $2,000 for this kind of content.",
        negotiation_context="We offered $1,500 for 1 TikTok video.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.COUNTER
    assert result.proposed_rate == "2000.00"
    assert result.confidence >= 0.8


# --- Test COUNTER intent with deliverable change ---


def test_classify_counter_with_deliverables(mock_anthropic_client: MagicMock) -> None:
    """Counter with deliverable change populates proposed_deliverables."""
    classification = IntentClassification(
        intent=NegotiationIntent.COUNTER,
        confidence=0.88,
        proposed_rate=None,
        proposed_deliverables=[
            ProposedDeliverable(deliverable_type="instagram_reel", quantity=2),
        ],
        summary="Influencer proposes 2 reels instead of 1.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="Could we do 2 reels instead of 1? I think that'd be better.",
        negotiation_context="We offered $1,000 for 1 Instagram reel.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.COUNTER
    assert len(result.proposed_deliverables) == 1
    assert result.proposed_deliverables[0].deliverable_type == "instagram_reel"
    assert result.proposed_deliverables[0].quantity == 2


# --- Test REJECT intent ---


def test_classify_reject_intent(mock_anthropic_client: MagicMock) -> None:
    """Clear rejection returns REJECT with high confidence."""
    classification = IntentClassification(
        intent=NegotiationIntent.REJECT,
        confidence=0.90,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Influencer declines the partnership.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="I'll pass on this one, thanks.",
        negotiation_context="We offered $500 for 1 Instagram post.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.REJECT
    assert result.confidence >= 0.8


# --- Test QUESTION intent ---


def test_classify_question_intent(mock_anthropic_client: MagicMock) -> None:
    """Question about terms returns QUESTION with key_concerns populated."""
    classification = IntentClassification(
        intent=NegotiationIntent.QUESTION,
        confidence=0.85,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Influencer asks about partnership details.",
        key_concerns=["What does the partnership include?", "Timeline unclear"],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="What exactly does the partnership include? And what's the timeline?",
        negotiation_context="We offered $800 for 1 YouTube video.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.QUESTION
    assert len(result.key_concerns) == 2
    assert "What does the partnership include?" in result.key_concerns


# --- Test low confidence override to UNCLEAR ---


def test_low_confidence_overrides_to_unclear(mock_anthropic_client: MagicMock) -> None:
    """When model confidence is below threshold, intent is overridden to UNCLEAR."""
    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.40,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Ambiguous response, maybe positive.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="Hmm, interesting. Let me think about it...",
        negotiation_context="We offered $1,000 for 1 reel.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.UNCLEAR
    assert result.confidence == 0.40


# --- Test UNCLEAR stays UNCLEAR (no double override) ---


def test_unclear_intent_not_overridden(mock_anthropic_client: MagicMock) -> None:
    """When model returns UNCLEAR, it stays UNCLEAR regardless of confidence."""
    classification = IntentClassification(
        intent=NegotiationIntent.UNCLEAR,
        confidence=0.30,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Cannot determine intent.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="...",
        negotiation_context="Some context.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.UNCLEAR


# --- Test confidence at exactly threshold is NOT overridden ---


def test_confidence_at_threshold_not_overridden(
    mock_anthropic_client: MagicMock,
) -> None:
    """Confidence exactly at threshold (0.70) is NOT overridden (exclusive <)."""
    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.70,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Probably accepts.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    result = classify_intent(
        email_body="Yeah, I think that works.",
        negotiation_context="We offered $1,000.",
        client=mock_anthropic_client,
    )

    assert result.intent == NegotiationIntent.ACCEPT
    assert result.confidence == 0.70


# --- Test API call arguments ---


def test_parse_called_with_correct_arguments(
    mock_anthropic_client: MagicMock,
) -> None:
    """Verify client.messages.parse is called with correct model, format, system, messages."""
    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.95,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Accepts.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    context = "Offered $1,000 for 1 reel."
    email = "Sounds great!"

    classify_intent(
        email_body=email,
        negotiation_context=context,
        client=mock_anthropic_client,
    )

    mock_anthropic_client.messages.parse.assert_called_once()
    call_kwargs = mock_anthropic_client.messages.parse.call_args.kwargs

    assert call_kwargs["model"] == INTENT_MODEL
    assert call_kwargs["output_format"] == IntentClassification
    assert call_kwargs["system"] == INTENT_CLASSIFICATION_SYSTEM_PROMPT.format(
        negotiation_context=context
    )
    assert call_kwargs["max_tokens"] == 1024
    assert len(call_kwargs["messages"]) == 1
    assert call_kwargs["messages"][0]["role"] == "user"
    assert email in call_kwargs["messages"][0]["content"]


# --- Test custom model parameter ---


def test_custom_model_parameter(mock_anthropic_client: MagicMock) -> None:
    """Custom model string is passed through to client.messages.parse."""
    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.95,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Accepts.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    classify_intent(
        email_body="Sure!",
        negotiation_context="Context.",
        client=mock_anthropic_client,
        model="claude-sonnet-4-5-20250929",
    )

    call_kwargs = mock_anthropic_client.messages.parse.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"


# --- Test custom confidence threshold ---


def test_custom_confidence_threshold(mock_anthropic_client: MagicMock) -> None:
    """Custom confidence threshold overrides default 0.70."""
    classification = IntentClassification(
        intent=NegotiationIntent.ACCEPT,
        confidence=0.55,
        proposed_rate=None,
        proposed_deliverables=[],
        summary="Maybe accepts.",
        key_concerns=[],
    )
    mock_anthropic_client.messages.parse.return_value = make_mock_parse_response(
        classification
    )

    # With threshold=0.50, confidence=0.55 should NOT be overridden
    result = classify_intent(
        email_body="I guess so.",
        negotiation_context="Context.",
        client=mock_anthropic_client,
        confidence_threshold=0.50,
    )

    assert result.intent == NegotiationIntent.ACCEPT

    # With threshold=0.60, confidence=0.55 SHOULD be overridden
    result = classify_intent(
        email_body="I guess so.",
        negotiation_context="Context.",
        client=mock_anthropic_client,
        confidence_threshold=0.60,
    )

    assert result.intent == NegotiationIntent.UNCLEAR
