"""LLM integration package for influencer negotiation agent.

Provides Anthropic client configuration, Pydantic models for LLM I/O,
system prompt templates, knowledge base loading, intent classification,
email composition, deterministic validation gate, and end-to-end negotiation
loop orchestrator.
"""

from negotiation.llm.client import (
    COMPOSE_MODEL,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_ROUNDS,
    INTENT_MODEL,
    get_anthropic_client,
)
from negotiation.llm.composer import compose_counter_email
from negotiation.llm.intent import classify_intent
from negotiation.llm.knowledge_base import list_available_platforms, load_knowledge_base
from negotiation.llm.models import (
    AgreementPayload,
    ComposedEmail,
    EscalationPayload,
    IntentClassification,
    NegotiationIntent,
    ProposedDeliverable,
    ValidationFailure,
    ValidationResult,
)
from negotiation.llm.negotiation_loop import process_influencer_reply
from negotiation.llm.validation import validate_composed_email

__all__ = [
    "COMPOSE_MODEL",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_MAX_ROUNDS",
    "INTENT_MODEL",
    "AgreementPayload",
    "ComposedEmail",
    "EscalationPayload",
    "IntentClassification",
    "NegotiationIntent",
    "ProposedDeliverable",
    "ValidationFailure",
    "ValidationResult",
    "classify_intent",
    "compose_counter_email",
    "get_anthropic_client",
    "list_available_platforms",
    "load_knowledge_base",
    "process_influencer_reply",
    "validate_composed_email",
]
