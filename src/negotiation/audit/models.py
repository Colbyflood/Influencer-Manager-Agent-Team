"""Audit trail models for tracking all negotiation events.

Per locked decision: Full context per entry including event type, campaign/influencer
identifiers, thread info, email body, negotiation state, rates, intent classification,
and arbitrary metadata.
"""

from enum import StrEnum

from pydantic import BaseModel


class EventType(StrEnum):
    """Types of events tracked in the audit trail."""

    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    STATE_TRANSITION = "state_transition"
    ESCALATION = "escalation"
    AGREEMENT = "agreement"
    TAKEOVER = "takeover"
    CAMPAIGN_START = "campaign_start"
    CAMPAIGN_INFLUENCER_SKIP = "campaign_influencer_skip"
    ERROR = "error"


class AuditEntry(BaseModel):
    """A single audit trail entry with full negotiation context.

    All fields except event_type are optional to accommodate different
    event types (e.g., campaign_start won't have thread_id).
    """

    event_type: EventType
    campaign_id: str | None = None
    influencer_name: str | None = None
    thread_id: str | None = None
    direction: str | None = None
    email_body: str | None = None
    negotiation_state: str | None = None
    rates_used: str | None = None
    intent_classification: str | None = None
    metadata: dict[str, str] | None = None
