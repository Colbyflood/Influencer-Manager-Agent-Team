"""Tests for the GmailClient Gmail API wrapper."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from negotiation.email.client import GmailClient
from negotiation.email.models import (
    EmailThreadContext,
    InboundEmail,
    OutboundEmail,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FROM_EMAIL = "agent@company.com"
TO_EMAIL = "influencer@example.com"
THREAD_ID = "thread_xyz789"
MESSAGE_ID_HEADER = "<msg789@mail.gmail.com>"
SUBJECT = "Partnership Proposal"


def _make_service() -> MagicMock:
    """Create a mock Gmail API service."""
    return MagicMock()


def _make_client(service: MagicMock | None = None) -> GmailClient:
    """Create a GmailClient with a mock service."""
    if service is None:
        service = _make_service()
    return GmailClient(service=service, from_email=FROM_EMAIL)


def _make_raw_email(
    body: str = "Hello from the test",
    subject: str = SUBJECT,
    from_addr: str = TO_EMAIL,
) -> str:
    """Create a base64url-encoded raw email for API mock responses."""
    msg = EmailMessage()
    msg.set_content(body)
    msg["From"] = from_addr
    msg["To"] = FROM_EMAIL
    msg["Subject"] = subject
    msg["Message-ID"] = MESSAGE_ID_HEADER
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


# ---------------------------------------------------------------------------
# GmailClient.send tests
# ---------------------------------------------------------------------------


class TestGmailClientSend:
    """Tests for GmailClient.send."""

    def test_calls_messages_send(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(to=TO_EMAIL, subject=SUBJECT, body="Hi there")

        client.send(outbound)

        service.users().messages().send.assert_called_once()

    def test_sends_base64url_encoded_raw(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(to=TO_EMAIL, subject=SUBJECT, body="Hi there")

        client.send(outbound)

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"] if "body" in call_args[1] else call_args[0][0]
        raw = payload["raw"]
        # Should be valid base64url
        decoded = base64.urlsafe_b64decode(raw)
        assert b"Hi there" in decoded

    def test_sets_thread_id_when_provided(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(
            to=TO_EMAIL,
            subject=SUBJECT,
            body="Reply",
            thread_id=THREAD_ID,
        )

        client.send(outbound)

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        assert payload["threadId"] == THREAD_ID

    def test_no_thread_id_when_not_provided(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(to=TO_EMAIL, subject=SUBJECT, body="New email")

        client.send(outbound)

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        assert "threadId" not in payload

    def test_sets_in_reply_to_header(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(
            to=TO_EMAIL,
            subject=SUBJECT,
            body="Reply",
            in_reply_to=MESSAGE_ID_HEADER,
            references=MESSAGE_ID_HEADER,
        )

        client.send(outbound)

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        decoded = base64.urlsafe_b64decode(payload["raw"])
        assert b"In-Reply-To" in decoded
        assert MESSAGE_ID_HEADER.encode() in decoded

    def test_sets_references_header(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(
            to=TO_EMAIL,
            subject=SUBJECT,
            body="Reply",
            in_reply_to=MESSAGE_ID_HEADER,
            references=MESSAGE_ID_HEADER,
        )

        client.send(outbound)

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        decoded = base64.urlsafe_b64decode(payload["raw"])
        assert b"References" in decoded

    def test_sets_from_header(self) -> None:
        service = _make_service()
        client = _make_client(service)
        outbound = OutboundEmail(to=TO_EMAIL, subject=SUBJECT, body="Hi")

        client.send(outbound)

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        decoded = base64.urlsafe_b64decode(payload["raw"])
        assert FROM_EMAIL.encode() in decoded

    def test_returns_api_response(self) -> None:
        service = _make_service()
        expected = {"id": "msg123", "threadId": THREAD_ID, "labelIds": ["SENT"]}
        service.users().messages().send().execute.return_value = expected
        client = _make_client(service)
        outbound = OutboundEmail(to=TO_EMAIL, subject=SUBJECT, body="Hi")

        result = client.send(outbound)

        assert result == expected


# ---------------------------------------------------------------------------
# GmailClient.send_reply tests
# ---------------------------------------------------------------------------


class TestGmailClientSendReply:
    """Tests for GmailClient.send_reply."""

    @patch("negotiation.email.client.get_thread_context")
    def test_calls_get_thread_context(self, mock_ctx: MagicMock) -> None:
        mock_ctx.return_value = EmailThreadContext(
            thread_id=THREAD_ID,
            last_message_id=MESSAGE_ID_HEADER,
            subject=SUBJECT,
            influencer_email=TO_EMAIL,
        )
        service = _make_service()
        client = _make_client(service)

        client.send_reply(THREAD_ID, "Thanks!")

        mock_ctx.assert_called_once_with(service, THREAD_ID)

    @patch("negotiation.email.client.get_thread_context")
    def test_sends_with_reply_headers(self, mock_ctx: MagicMock) -> None:
        mock_ctx.return_value = EmailThreadContext(
            thread_id=THREAD_ID,
            last_message_id=MESSAGE_ID_HEADER,
            subject=SUBJECT,
            influencer_email=TO_EMAIL,
        )
        service = _make_service()
        client = _make_client(service)

        client.send_reply(THREAD_ID, "Thanks!")

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        assert payload["threadId"] == THREAD_ID
        decoded = base64.urlsafe_b64decode(payload["raw"])
        assert b"In-Reply-To" in decoded

    @patch("negotiation.email.client.get_thread_context")
    def test_adds_re_prefix_to_subject(self, mock_ctx: MagicMock) -> None:
        mock_ctx.return_value = EmailThreadContext(
            thread_id=THREAD_ID,
            last_message_id=MESSAGE_ID_HEADER,
            subject="Original Subject",
            influencer_email=TO_EMAIL,
        )
        service = _make_service()
        client = _make_client(service)

        client.send_reply(THREAD_ID, "Thanks!")

        call_args = service.users().messages().send.call_args
        payload = call_args[1]["body"]
        decoded = base64.urlsafe_b64decode(payload["raw"])
        assert b"Re: Original Subject" in decoded

    @patch("negotiation.email.client.get_thread_context")
    def test_returns_send_response(self, mock_ctx: MagicMock) -> None:
        mock_ctx.return_value = EmailThreadContext(
            thread_id=THREAD_ID,
            last_message_id=MESSAGE_ID_HEADER,
            subject=SUBJECT,
            influencer_email=TO_EMAIL,
        )
        service = _make_service()
        expected = {"id": "reply_msg", "threadId": THREAD_ID}
        service.users().messages().send().execute.return_value = expected
        client = _make_client(service)

        result = client.send_reply(THREAD_ID, "Thanks!")

        assert result == expected


# ---------------------------------------------------------------------------
# GmailClient.setup_watch tests
# ---------------------------------------------------------------------------


class TestGmailClientSetupWatch:
    """Tests for GmailClient.setup_watch."""

    def test_calls_watch_with_correct_body(self) -> None:
        service = _make_service()
        client = _make_client(service)
        topic = "projects/my-project/topics/gmail-notifs"

        client.setup_watch(topic)

        service.users().watch.assert_called_once_with(
            userId="me",
            body={
                "labelIds": ["INBOX"],
                "topicName": topic,
                "labelFilterBehavior": "INCLUDE",
            },
        )

    def test_returns_history_id_and_expiration(self) -> None:
        service = _make_service()
        expected = {"historyId": "12345", "expiration": "1234567890000"}
        service.users().watch().execute.return_value = expected
        client = _make_client(service)

        result = client.setup_watch("projects/p/topics/t")

        assert result["historyId"] == "12345"
        assert result["expiration"] == "1234567890000"


# ---------------------------------------------------------------------------
# GmailClient.fetch_new_messages tests
# ---------------------------------------------------------------------------


class TestGmailClientFetchNewMessages:
    """Tests for GmailClient.fetch_new_messages."""

    def test_extracts_message_ids_from_history(self) -> None:
        service = _make_service()
        service.users().history().list().execute.return_value = {
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "msg_1"}},
                        {"message": {"id": "msg_2"}},
                    ]
                },
                {
                    "messagesAdded": [
                        {"message": {"id": "msg_3"}},
                    ]
                },
            ],
            "historyId": "99999",
        }
        client = _make_client(service)

        ids, new_history_id = client.fetch_new_messages("10000")

        assert ids == ["msg_1", "msg_2", "msg_3"]
        assert new_history_id == "99999"

    def test_empty_history_returns_empty_list(self) -> None:
        service = _make_service()
        service.users().history().list().execute.return_value = {
            "historyId": "10000",
        }
        client = _make_client(service)

        ids, new_history_id = client.fetch_new_messages("10000")

        assert ids == []
        assert new_history_id == "10000"

    def test_calls_history_list_with_correct_params(self) -> None:
        service = _make_service()
        service.users().history().list().execute.return_value = {
            "historyId": "10000",
        }
        client = _make_client(service)

        client.fetch_new_messages("5000")

        service.users().history().list.assert_called_with(
            userId="me",
            startHistoryId="5000",
            historyTypes=["messageAdded"],
        )

    def test_mixed_history_records(self) -> None:
        """History can have records without messagesAdded."""
        service = _make_service()
        service.users().history().list().execute.return_value = {
            "history": [
                {"labelsAdded": [{"message": {"id": "skip"}}]},
                {"messagesAdded": [{"message": {"id": "msg_1"}}]},
            ],
            "historyId": "20000",
        }
        client = _make_client(service)

        ids, _ = client.fetch_new_messages("10000")

        assert ids == ["msg_1"]


# ---------------------------------------------------------------------------
# GmailClient.get_message tests
# ---------------------------------------------------------------------------


class TestGmailClientGetMessage:
    """Tests for GmailClient.get_message."""

    def _setup_service_for_get_message(
        self,
        service: MagicMock,
        *,
        body: str = "Test reply body",
        subject: str = SUBJECT,
        from_email: str = TO_EMAIL,
        thread_id: str = THREAD_ID,
        internal_date: str = "1704067200000",  # 2024-01-01T00:00:00Z
    ) -> None:
        """Configure mock service for get_message calls."""
        raw = _make_raw_email(body=body, subject=subject, from_addr=from_email)

        # First call: format="raw"
        raw_response = {
            "raw": raw,
            "threadId": thread_id,
            "internalDate": internal_date,
        }

        # Second call: format="metadata"
        meta_response = {
            "payload": {
                "headers": [
                    {"name": "Message-ID", "value": MESSAGE_ID_HEADER},
                    {"name": "From", "value": from_email},
                    {"name": "Subject", "value": subject},
                ]
            }
        }

        service.users().messages().get().execute.side_effect = [
            raw_response,
            meta_response,
        ]

    def test_returns_inbound_email(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service)
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert isinstance(result, InboundEmail)

    def test_parses_body_text(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service, body="I accept $500")
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert "I accept $500" in result.body_text

    def test_extracts_from_email(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service, from_email="star@example.com")
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert result.from_email == "star@example.com"

    def test_extracts_subject(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service, subject="Deal Discussion")
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert result.subject == "Deal Discussion"

    def test_extracts_message_id_header(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service)
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert result.message_id_header == MESSAGE_ID_HEADER

    def test_extracts_thread_id(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service, thread_id="thread_abc")
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert result.thread_id == "thread_abc"

    def test_converts_internal_date_to_iso(self) -> None:
        service = _make_service()
        # 2024-01-01T00:00:00Z in milliseconds
        self._setup_service_for_get_message(service, internal_date="1704067200000")
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert "2024-01-01" in result.received_at

    def test_gmail_message_id_set(self) -> None:
        service = _make_service()
        self._setup_service_for_get_message(service)
        client = _make_client(service)

        result = client.get_message("msg_123")

        assert result.gmail_message_id == "msg_123"
