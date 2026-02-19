"""LLM integration package for influencer negotiation agent.

Provides Anthropic client configuration, Pydantic models for LLM I/O,
system prompt templates, and knowledge base loading.
"""

from negotiation.llm.client import COMPOSE_MODEL, INTENT_MODEL, get_anthropic_client
from negotiation.llm.models import (
    ComposedEmail,
    EscalationPayload,
    IntentClassification,
    NegotiationIntent,
    ProposedDeliverable,
    ValidationFailure,
    ValidationResult,
)

__all__ = [
    "COMPOSE_MODEL",
    "INTENT_MODEL",
    "ComposedEmail",
    "EscalationPayload",
    "IntentClassification",
    "NegotiationIntent",
    "ProposedDeliverable",
    "ValidationFailure",
    "ValidationResult",
    "get_anthropic_client",
]
