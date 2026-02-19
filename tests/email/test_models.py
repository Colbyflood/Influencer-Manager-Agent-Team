"""Tests for the email domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from negotiation.email.models import EmailThreadContext, InboundEmail, OutboundEmail

# ---------------------------------------------------------------------------
# EmailThreadContext
# ---------------------------------------------------------------------------


class TestEmailThreadContext:
    """Tests for EmailThreadContext model."""

    def test_create_valid(self):
        """Creates an EmailThreadContext with all required fields."""
        ctx = EmailThreadContext(
            thread_id="thread_abc",
            last_message_id="<msg123@example.com>",
            subject="Partnership Inquiry",
            influencer_email="influencer@example.com",
        )
        assert ctx.thread_id == "thread_abc"
        assert ctx.last_message_id == "<msg123@example.com>"
        assert ctx.subject == "Partnership Inquiry"
        assert ctx.influencer_email == "influencer@example.com"

    def test_frozen_immutability(self):
        """Cannot mutate fields on a frozen model."""
        ctx = EmailThreadContext(
            thread_id="t1",
            last_message_id="<m1@x.com>",
            subject="Test",
            influencer_email="a@b.com",
        )
        with pytest.raises(ValidationError):
            ctx.thread_id = "changed"

    def test_requires_thread_id(self):
        """Raises ValidationError when thread_id is missing."""
        with pytest.raises(ValidationError):
            EmailThreadContext(
                last_message_id="<m1@x.com>",
                subject="Test",
                influencer_email="a@b.com",
            )  # type: ignore[call-arg]

    def test_requires_last_message_id(self):
        """Raises ValidationError when last_message_id is missing."""
        with pytest.raises(ValidationError):
            EmailThreadContext(
                thread_id="t1",
                subject="Test",
                influencer_email="a@b.com",
            )  # type: ignore[call-arg]

    def test_requires_subject(self):
        """Raises ValidationError when subject is missing."""
        with pytest.raises(ValidationError):
            EmailThreadContext(
                thread_id="t1",
                last_message_id="<m1@x.com>",
                influencer_email="a@b.com",
            )  # type: ignore[call-arg]

    def test_requires_influencer_email(self):
        """Raises ValidationError when influencer_email is missing."""
        with pytest.raises(ValidationError):
            EmailThreadContext(
                thread_id="t1",
                last_message_id="<m1@x.com>",
                subject="Test",
            )  # type: ignore[call-arg]

    def test_equality(self):
        """Two instances with same data are equal."""
        kwargs = {
            "thread_id": "t1",
            "last_message_id": "<m@x.com>",
            "subject": "Hi",
            "influencer_email": "a@b.com",
        }
        assert EmailThreadContext(**kwargs) == EmailThreadContext(**kwargs)


# ---------------------------------------------------------------------------
# InboundEmail
# ---------------------------------------------------------------------------


class TestInboundEmail:
    """Tests for InboundEmail model."""

    def _make(self, **overrides) -> InboundEmail:
        defaults = {
            "gmail_message_id": "msg_123",
            "thread_id": "thread_abc",
            "message_id_header": "<abc@mail.example.com>",
            "from_email": "influencer@example.com",
            "subject": "Re: Partnership",
            "body_text": "Sounds great!",
            "received_at": "2026-02-18T10:30:00Z",
        }
        defaults.update(overrides)
        return InboundEmail(**defaults)

    def test_create_valid(self):
        """Creates an InboundEmail with all required fields."""
        email = self._make()
        assert email.gmail_message_id == "msg_123"
        assert email.thread_id == "thread_abc"
        assert email.from_email == "influencer@example.com"
        assert email.received_at == "2026-02-18T10:30:00Z"

    def test_frozen_immutability(self):
        """Cannot mutate fields on a frozen model."""
        email = self._make()
        with pytest.raises(ValidationError):
            email.body_text = "changed"

    def test_requires_all_fields(self):
        """Raises ValidationError when any required field is missing."""
        with pytest.raises(ValidationError):
            InboundEmail(
                gmail_message_id="x",
                thread_id="t",
                # missing remaining fields
            )  # type: ignore[call-arg]

    def test_body_text_preserves_whitespace(self):
        """Body text preserves formatting and whitespace."""
        email = self._make(body_text="Line 1\n\nLine 3")
        assert email.body_text == "Line 1\n\nLine 3"

    def test_equality(self):
        """Two instances with same data are equal."""
        assert self._make() == self._make()


# ---------------------------------------------------------------------------
# OutboundEmail
# ---------------------------------------------------------------------------


class TestOutboundEmail:
    """Tests for OutboundEmail model."""

    def test_create_minimal(self):
        """Creates an OutboundEmail with only required fields."""
        email = OutboundEmail(
            to="influencer@example.com",
            subject="Partnership Inquiry",
            body="Hi, we'd like to work with you.",
        )
        assert email.to == "influencer@example.com"
        assert email.thread_id is None
        assert email.in_reply_to is None
        assert email.references is None

    def test_create_reply(self):
        """Creates an OutboundEmail configured as a thread reply."""
        email = OutboundEmail(
            to="influencer@example.com",
            subject="Re: Partnership Inquiry",
            body="Thanks for getting back to us!",
            thread_id="thread_abc",
            in_reply_to="<msg1@example.com>",
            references="<msg0@example.com> <msg1@example.com>",
        )
        assert email.thread_id == "thread_abc"
        assert email.in_reply_to == "<msg1@example.com>"
        assert email.references == "<msg0@example.com> <msg1@example.com>"

    def test_frozen_immutability(self):
        """Cannot mutate fields on a frozen model."""
        email = OutboundEmail(to="a@b.com", subject="S", body="B")
        with pytest.raises(ValidationError):
            email.to = "changed@b.com"

    def test_optional_fields_default_none(self):
        """thread_id, in_reply_to, references default to None."""
        email = OutboundEmail(to="a@b.com", subject="S", body="B")
        assert email.thread_id is None
        assert email.in_reply_to is None
        assert email.references is None

    def test_requires_to(self):
        """Raises ValidationError when 'to' is missing."""
        with pytest.raises(ValidationError):
            OutboundEmail(subject="S", body="B")  # type: ignore[call-arg]

    def test_requires_subject(self):
        """Raises ValidationError when 'subject' is missing."""
        with pytest.raises(ValidationError):
            OutboundEmail(to="a@b.com", body="B")  # type: ignore[call-arg]

    def test_requires_body(self):
        """Raises ValidationError when 'body' is missing."""
        with pytest.raises(ValidationError):
            OutboundEmail(to="a@b.com", subject="S")  # type: ignore[call-arg]

    def test_equality(self):
        """Two instances with same data are equal."""
        kwargs = {"to": "a@b.com", "subject": "S", "body": "B"}
        assert OutboundEmail(**kwargs) == OutboundEmail(**kwargs)
