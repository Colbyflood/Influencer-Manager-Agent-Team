"""Pydantic models defining structured I/O contracts for LLM interactions.

These models are used for:
- Intent classification (structured output from Claude)
- Email composition result tracking
- Deterministic validation gate results
- Human escalation payloads
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class NegotiationIntent(StrEnum):
    """The influencer's negotiation intent extracted from their email."""

    ACCEPT = "accept"
    COUNTER = "counter"
    REJECT = "reject"
    QUESTION = "question"
    UNCLEAR = "unclear"


class ProposedDeliverable(BaseModel):
    """A deliverable mentioned or proposed in the influencer's reply."""

    deliverable_type: str = Field(
        description="The type of deliverable (e.g., 'instagram_reel', 'tiktok_video')"
    )
    quantity: int = Field(
        default=1,
        description="Number of this deliverable type proposed",
    )


class IntentClassification(BaseModel):
    """Structured extraction from an influencer email reply.

    Used with Anthropic structured outputs (client.messages.parse()) to guarantee
    schema-compliant extraction of negotiation intent from free-text emails.
    """

    intent: NegotiationIntent = Field(description="The primary negotiation intent of the email")
    confidence: float = Field(
        description="Confidence in the intent classification (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    proposed_rate: str | None = Field(
        default=None,
        description=(
            "The dollar amount proposed by the influencer, as a string "
            "(e.g., '1500.00'). None if no rate mentioned."
        ),
    )
    proposed_deliverables: list[ProposedDeliverable] = Field(
        default_factory=list,
        description=(
            "Deliverables mentioned or proposed by the influencer. Empty if no changes proposed."
        ),
    )
    summary: str = Field(description="One-sentence summary of what the influencer is saying")
    key_concerns: list[str] = Field(
        default_factory=list,
        description="Any concerns, conditions, or questions raised by the influencer",
    )


class ComposedEmail(BaseModel):
    """Result of LLM email composition including token usage tracking."""

    email_body: str = Field(description="The composed email body text")
    model_used: str = Field(description="The model ID used for composition")
    input_tokens: int = Field(description="Number of input tokens consumed")
    output_tokens: int = Field(description="Number of output tokens generated")


class ValidationFailure(BaseModel):
    """A single validation check failure from the deterministic validation gate."""

    check: str = Field(description="Name of the validation check that failed")
    reason: str = Field(description="Human-readable explanation of the failure")
    severity: str = Field(
        default="error",
        description="Severity level: 'error' blocks send, 'warning' logs but allows",
    )


class ValidationResult(BaseModel):
    """Result of running all validation checks on a composed email.

    The validation gate is entirely deterministic -- no LLM involved.
    """

    passed: bool = Field(description="Whether all error-severity checks passed")
    failures: list[ValidationFailure] = Field(
        default_factory=list,
        description="List of validation failures found",
    )
    email_body: str = Field(description="The email body that was validated")


class EscalationPayload(BaseModel):
    """Data structure for human escalation when validation fails or confidence is low.

    Consumed by Phase 4 (Slack escalation) to present draft + context to human reviewers.

    Phase 3 fields: reason, email_draft, validation_failures,
    influencer_name, thread_id, proposed_rate, our_rate.

    Phase 4 additions: influencer_email, client_name, evidence_quote,
    suggested_actions, trigger_type.
    """

    reason: str = Field(description="Why escalation was triggered")
    email_draft: str = Field(description="The composed email draft for human review")
    validation_failures: list[ValidationFailure] = Field(
        default_factory=list,
        description="Validation failures that triggered escalation",
    )
    influencer_name: str = Field(description="Name of the influencer being negotiated with")
    thread_id: str = Field(description="Email thread identifier for context")
    proposed_rate: Decimal | None = Field(
        default=None,
        description="The influencer's proposed rate, if any",
    )
    our_rate: Decimal | None = Field(
        default=None,
        description="Our counter-offer rate, if any",
    )
    # Phase 4 additions (defaults for backward compatibility with Phase 3)
    influencer_email: str = Field(
        default="",
        description="Influencer's email address for Slack notifications",
    )
    client_name: str = Field(
        default="",
        description="Client/brand name for Slack notifications",
    )
    evidence_quote: str = Field(
        default="",
        description="Quote from the email that triggered escalation",
    )
    suggested_actions: list[str] = Field(
        default_factory=list,
        description="Suggested actions for the human reviewer",
    )
    trigger_type: str = Field(
        default="",
        description="The type of trigger that caused escalation",
    )


class AgreementPayload(BaseModel):
    """Data for agreement Slack notifications (HUMAN-03).

    Constructed by the Phase 4 orchestration layer by combining data from
    IntentClassification, the negotiation context, and the pricing engine.
    """

    influencer_name: str = Field(description="Name of the influencer")
    influencer_email: str = Field(description="Influencer's email address")
    client_name: str = Field(description="Client/brand name")
    agreed_rate: Decimal = Field(description="The agreed-upon rate")
    platform: str = Field(description="Social media platform")
    deliverables: str = Field(description="Description of agreed deliverables")
    cpm_achieved: Decimal = Field(description="CPM achieved with the agreed rate")
    thread_id: str = Field(description="Email thread identifier")
    next_steps: list[str] = Field(
        default_factory=list,
        description="Next steps after agreement (e.g., 'Send contract')",
    )
    mention_users: list[str] = Field(
        default_factory=list,
        description="Slack user IDs to @ mention on agreement alerts",
    )
