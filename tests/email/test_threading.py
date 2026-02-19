"""Tests for email thread context extraction and reply header building."""

from __future__ import annotations

from unittest.mock import MagicMock

from negotiation.email.models import EmailThreadContext
from negotiation.email.threading import build_reply_headers, get_thread_context

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

THREAD_ID = "thread_abc123"
MESSAGE_ID = "<msg123@mail.gmail.com>"
SUBJECT = "Partnership Proposal"
FROM_EMAIL = "influencer@example.com"


def _make_mock_service(
    *,
    thread_id: str = THREAD_ID,
    headers: list[dict[str, str]] | None = None,
    messages: list[dict] | None = None,
) -> MagicMock:
    """Build a mock Gmail API service returning a thread with given headers."""
    if headers is None:
        headers = [
            {"name": "Message-ID", "value": MESSAGE_ID},
            {"name": "Subject", "value": SUBJECT},
            {"name": "From", "value": FROM_EMAIL},
        ]

    if messages is None:
        messages = [{"payload": {"headers": headers}}]

    service = MagicMock()
    (
        service.users()
        .threads()
        .get()
        .execute.return_value
    ) = {"messages": messages}
    return service


def _make_thread_ctx(
    *,
    thread_id: str = THREAD_ID,
    last_message_id: str = MESSAGE_ID,
    subject: str = SUBJECT,
    influencer_email: str = FROM_EMAIL,
) -> EmailThreadContext:
    return EmailThreadContext(
        thread_id=thread_id,
        last_message_id=last_message_id,
        subject=subject,
        influencer_email=influencer_email,
    )


# ---------------------------------------------------------------------------
# get_thread_context tests
# ---------------------------------------------------------------------------


class TestGetThreadContext:
    """Tests for get_thread_context."""

    def test_extracts_thread_id(self) -> None:
        service = _make_mock_service()
        ctx = get_thread_context(service, THREAD_ID)
        assert ctx.thread_id == THREAD_ID

    def test_extracts_message_id(self) -> None:
        service = _make_mock_service()
        ctx = get_thread_context(service, THREAD_ID)
        assert ctx.last_message_id == MESSAGE_ID

    def test_extracts_subject(self) -> None:
        service = _make_mock_service()
        ctx = get_thread_context(service, THREAD_ID)
        assert ctx.subject == SUBJECT

    def test_extracts_from_email(self) -> None:
        service = _make_mock_service()
        ctx = get_thread_context(service, THREAD_ID)
        assert ctx.influencer_email == FROM_EMAIL

    def test_uses_last_message_in_thread(self) -> None:
        """When multiple messages exist, headers come from the last one."""
        old_headers = [
            {"name": "Message-ID", "value": "<old@mail.gmail.com>"},
            {"name": "Subject", "value": "Old Subject"},
            {"name": "From", "value": "old@example.com"},
        ]
        new_headers = [
            {"name": "Message-ID", "value": "<new@mail.gmail.com>"},
            {"name": "Subject", "value": "New Subject"},
            {"name": "From", "value": "new@example.com"},
        ]
        messages = [
            {"payload": {"headers": old_headers}},
            {"payload": {"headers": new_headers}},
        ]
        service = _make_mock_service(messages=messages)
        ctx = get_thread_context(service, THREAD_ID)
        assert ctx.last_message_id == "<new@mail.gmail.com>"
        assert ctx.subject == "New Subject"
        assert ctx.influencer_email == "new@example.com"

    def test_missing_headers_default_to_empty(self) -> None:
        """Missing headers should default to empty strings."""
        service = _make_mock_service(headers=[])
        ctx = get_thread_context(service, THREAD_ID)
        assert ctx.last_message_id == ""
        assert ctx.subject == ""
        assert ctx.influencer_email == ""

    def test_calls_api_with_correct_params(self) -> None:
        """Verify the Gmail API is called with the right arguments."""
        service = _make_mock_service()
        get_thread_context(service, THREAD_ID)
        service.users().threads().get.assert_called_with(
            userId="me",
            id=THREAD_ID,
            format="metadata",
            metadataHeaders=["Message-ID", "Subject", "From"],
        )

    def test_returns_email_thread_context_type(self) -> None:
        service = _make_mock_service()
        ctx = get_thread_context(service, THREAD_ID)
        assert isinstance(ctx, EmailThreadContext)


# ---------------------------------------------------------------------------
# build_reply_headers tests
# ---------------------------------------------------------------------------


class TestBuildReplyHeaders:
    """Tests for build_reply_headers."""

    def test_in_reply_to_header(self) -> None:
        ctx = _make_thread_ctx()
        headers = build_reply_headers(ctx)
        assert headers["In-Reply-To"] == MESSAGE_ID

    def test_references_header(self) -> None:
        ctx = _make_thread_ctx()
        headers = build_reply_headers(ctx)
        assert headers["References"] == MESSAGE_ID

    def test_to_header(self) -> None:
        ctx = _make_thread_ctx()
        headers = build_reply_headers(ctx)
        assert headers["To"] == FROM_EMAIL

    def test_subject_gets_re_prefix(self) -> None:
        ctx = _make_thread_ctx(subject="Partnership Proposal")
        headers = build_reply_headers(ctx)
        assert headers["Subject"] == "Re: Partnership Proposal"

    def test_subject_no_duplicate_re_prefix(self) -> None:
        ctx = _make_thread_ctx(subject="Re: Partnership Proposal")
        headers = build_reply_headers(ctx)
        assert headers["Subject"] == "Re: Partnership Proposal"

    def test_subject_case_insensitive_re_check(self) -> None:
        ctx = _make_thread_ctx(subject="RE: Partnership Proposal")
        headers = build_reply_headers(ctx)
        assert headers["Subject"] == "RE: Partnership Proposal"

    def test_subject_re_with_different_casing(self) -> None:
        ctx = _make_thread_ctx(subject="re: Partnership Proposal")
        headers = build_reply_headers(ctx)
        assert headers["Subject"] == "re: Partnership Proposal"

    def test_returns_four_headers(self) -> None:
        ctx = _make_thread_ctx()
        headers = build_reply_headers(ctx)
        assert set(headers.keys()) == {"In-Reply-To", "References", "Subject", "To"}

    def test_empty_subject_gets_re_prefix(self) -> None:
        ctx = _make_thread_ctx(subject="")
        headers = build_reply_headers(ctx)
        assert headers["Subject"] == "Re: "
