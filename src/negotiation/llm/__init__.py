"""LLM integration package for influencer negotiation agent.

Provides Anthropic client configuration, Pydantic models for LLM I/O,
system prompt templates, knowledge base loading, email composition,
and deterministic validation gate.
"""

from negotiation.llm.client import COMPOSE_MODEL, INTENT_MODEL, get_anthropic_client
from negotiation.llm.composer import compose_counter_email
from negotiation.llm.intent import classify_intent
from negotiation.llm.models import (
    ComposedEmail,
    EscalationPayload,
    IntentClassification,
    NegotiationIntent,
    ProposedDeliverable,
    ValidationFailure,
    ValidationResult,
)
from negotiation.llm.validation import validate_composed_email

__all__ = [
    "COMPOSE_MODEL",
    "INTENT_MODEL",
    "ComposedEmail",
    "EscalationPayload",
    "classify_intent",
    "IntentClassification",
    "NegotiationIntent",
    "ProposedDeliverable",
    "ValidationFailure",
    "ValidationResult",
    "compose_counter_email",
    "get_anthropic_client",
    "validate_composed_email",
]
