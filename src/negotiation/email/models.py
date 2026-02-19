"""Pydantic v2 models for the email domain.

Provides frozen (immutable) models for representing email threads, inbound
messages, and outbound messages in the negotiation pipeline.
"""

from pydantic import BaseModel, ConfigDict


class EmailThreadContext(BaseModel):
    """Context for an ongoing email negotiation thread.

    Captures the minimal metadata needed to continue a conversation thread
    via the Gmail API (thread ID, last Message-ID header, subject, and
    the influencer's email address).
    """

    model_config = ConfigDict(frozen=True)

    thread_id: str
    last_message_id: str  # RFC 2822 Message-ID header
    subject: str
    influencer_email: str


class InboundEmail(BaseModel):
    """An inbound email message received from an influencer.

    Represents a single message parsed from the Gmail API response,
    including both Gmail-internal identifiers and standard email headers.
    """

    model_config = ConfigDict(frozen=True)

    gmail_message_id: str
    thread_id: str
    message_id_header: str  # RFC 2822 Message-ID header
    from_email: str
    subject: str
    body_text: str
    received_at: str  # ISO 8601


class OutboundEmail(BaseModel):
    """An outbound email message to be sent to an influencer.

    When ``thread_id``, ``in_reply_to``, and ``references`` are provided,
    the email is threaded as a reply.  Otherwise it is sent as a new
    conversation.
    """

    model_config = ConfigDict(frozen=True)

    to: str
    subject: str
    body: str
    thread_id: str | None = None
    in_reply_to: str | None = None  # RFC 2822 Message-ID to reply to
    references: str | None = None  # Space-separated RFC 2822 Message-IDs
