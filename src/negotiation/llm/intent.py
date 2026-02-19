"""Intent classification using Claude structured outputs.

Extracts negotiation intent, rate proposals, deliverable changes, and key
concerns from free-text influencer email replies.
"""

from __future__ import annotations

from anthropic import Anthropic

from negotiation.llm.client import DEFAULT_CONFIDENCE_THRESHOLD, INTENT_MODEL
from negotiation.llm.models import IntentClassification, NegotiationIntent
from negotiation.llm.prompts import INTENT_CLASSIFICATION_SYSTEM_PROMPT


def classify_intent(
    email_body: str,
    negotiation_context: str,
    client: Anthropic,
    *,
    model: str = INTENT_MODEL,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> IntentClassification:
    """Classify the negotiation intent of an influencer email reply.

    Uses Claude's structured outputs (``client.messages.parse()``) to extract
    a validated ``IntentClassification`` from the email body.  If the model's
    confidence falls below *confidence_threshold* and the predicted intent is
    not already ``UNCLEAR``, the intent is overridden to ``UNCLEAR`` for human
    escalation.

    Args:
        email_body: The raw text of the influencer's email reply.
        negotiation_context: A summary of the current negotiation state
            (e.g., "Offered $1,000 for 1 Instagram reel").
        client: An ``anthropic.Anthropic`` instance (or compatible mock).
        model: The Anthropic model ID to use.  Defaults to ``INTENT_MODEL``
            (Haiku for speed).
        confidence_threshold: Minimum confidence for the intent to stand.
            Below this value the intent is overridden to ``UNCLEAR``.
            Comparison is exclusive (``<``), so a value exactly at the
            threshold is *not* overridden.  Defaults to
            ``DEFAULT_CONFIDENCE_THRESHOLD`` (0.70).

    Returns:
        An ``IntentClassification`` with the detected intent, confidence,
        optional rate/deliverable proposals, summary, and key concerns.
    """
    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=INTENT_CLASSIFICATION_SYSTEM_PROMPT.format(
            negotiation_context=negotiation_context,
        ),
        messages=[
            {
                "role": "user",
                "content": (f"Classify the intent of this influencer email reply:\n\n{email_body}"),
            },
        ],
        output_format=IntentClassification,
    )

    parsed = response.parsed_output
    if parsed is None:  # pragma: no cover - structured outputs always return a result
        msg = "Anthropic structured output returned None"
        raise RuntimeError(msg)
    result: IntentClassification = parsed

    # Override low-confidence classifications to UNCLEAR for human escalation.
    # Skip if the model already classified as UNCLEAR.
    if result.confidence < confidence_threshold and result.intent != NegotiationIntent.UNCLEAR:
        result = result.model_copy(update={"intent": NegotiationIntent.UNCLEAR})

    return result
