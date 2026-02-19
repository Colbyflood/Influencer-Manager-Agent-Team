"""Gmail API client wrapper for sending, receiving, and watching emails.

Provides the ``GmailClient`` class that encapsulates all Gmail API
operations needed by the negotiation agent: composing and sending emails,
replying within threads, setting up Pub/Sub notifications, fetching new
messages from history, and decoding raw messages into domain models.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from negotiation.email.models import EmailThreadContext, InboundEmail, OutboundEmail
from negotiation.email.parser import extract_latest_reply, parse_mime_message
from negotiation.email.threading import build_reply_headers, get_thread_context


class GmailClient:
    """Wrapper around the Gmail API service for email operations.

    All methods operate through the provided Gmail API service resource
    (obtained via ``get_gmail_service``).  No real network calls are made
    by this class directly -- the service object handles transport.

    Args:
        service: An authenticated Gmail API v1 service resource.
        from_email: The email address to use as the ``From`` header.
    """

    def __init__(self, service: Any, from_email: str) -> None:
        self._service = service
        self._from_email = from_email

    def send(self, outbound: OutboundEmail) -> dict[str, Any]:
        """Compose and send an email via the Gmail API.

        Constructs an RFC 2822 MIME message from the ``OutboundEmail``
        model, base64url-encodes it, and sends via
        ``users.messages.send``.  When ``outbound.thread_id`` is set, the
        message is linked to an existing thread.  When
        ``outbound.in_reply_to`` is set, the corresponding threading
        headers are added.

        Args:
            outbound: The email to send.

        Returns:
            The Gmail API response dict (contains ``id``, ``threadId``,
            ``labelIds``).
        """
        message = EmailMessage()
        message.set_content(outbound.body)
        message["To"] = outbound.to
        message["From"] = self._from_email
        message["Subject"] = outbound.subject

        if outbound.in_reply_to:
            message["In-Reply-To"] = outbound.in_reply_to
        if outbound.references:
            message["References"] = outbound.references

        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        payload: dict[str, Any] = {"raw": encoded}

        if outbound.thread_id:
            payload["threadId"] = outbound.thread_id

        result: dict[str, Any] = (
            self._service.users().messages().send(userId="me", body=payload).execute()
        )
        return result

    def send_reply(self, thread_id: str, body: str) -> dict[str, Any]:
        """Send a reply within an existing email thread.

        Convenience method that fetches the thread context, builds
        appropriate reply headers, and sends the reply as a threaded
        message.

        Args:
            thread_id: The Gmail thread ID to reply in.
            body: The plain-text body of the reply.

        Returns:
            The Gmail API response dict from ``send``.
        """
        ctx: EmailThreadContext = get_thread_context(self._service, thread_id)
        headers = build_reply_headers(ctx)

        outbound = OutboundEmail(
            to=headers["To"],
            subject=headers["Subject"],
            body=body,
            thread_id=thread_id,
            in_reply_to=headers["In-Reply-To"],
            references=headers["References"],
        )
        return self.send(outbound)

    def setup_watch(self, topic_name: str) -> dict[str, Any]:
        """Register Gmail push notifications via Pub/Sub.

        Calls ``users.watch`` to start receiving notifications for inbox
        changes on the specified Pub/Sub topic.  The watch expires after
        7 days and must be renewed.

        Args:
            topic_name: The full Pub/Sub topic name, e.g.
                ``projects/my-project/topics/gmail-notifications``.

        Returns:
            The Gmail API response dict containing ``historyId`` and
            ``expiration``.
        """
        result: dict[str, Any] = (
            self._service.users()
            .watch(
                userId="me",
                body={
                    "labelIds": ["INBOX"],
                    "topicName": topic_name,
                    "labelFilterBehavior": "INCLUDE",
                },
            )
            .execute()
        )
        return result

    def fetch_new_messages(self, history_id: str) -> tuple[list[str], str]:
        """Fetch new message IDs since a given history ID.

        Calls ``users.history.list`` to retrieve mailbox changes since
        the provided ``history_id``.  Collects IDs of newly added
        messages.

        Args:
            history_id: The Gmail history ID to start from.

        Returns:
            A tuple of (list of new message IDs, latest history ID).
            If no new messages exist, returns an empty list with the
            original history ID.
        """
        response: dict[str, Any] = (
            self._service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=history_id,
                historyTypes=["messageAdded"],
            )
            .execute()
        )

        new_message_ids: list[str] = []
        for record in response.get("history", []):
            for msg_added in record.get("messagesAdded", []):
                new_message_ids.append(msg_added["message"]["id"])

        new_history_id = str(response.get("historyId", history_id))
        return new_message_ids, new_history_id

    def get_message(self, message_id: str) -> InboundEmail:
        """Fetch and parse a single Gmail message into an InboundEmail.

        Retrieves the raw message from the Gmail API, decodes the MIME
        structure to extract the text body, and extracts only the latest
        reply content.  Also fetches metadata headers for threading.

        Args:
            message_id: The Gmail message ID to fetch.

        Returns:
            An ``InboundEmail`` with parsed body text, headers, and
            timestamp.
        """
        msg: dict[str, Any] = (
            self._service.users().messages().get(userId="me", id=message_id, format="raw").execute()
        )

        raw_bytes = base64.urlsafe_b64decode(msg["raw"])
        full_body = parse_mime_message(raw_bytes)
        reply_text = extract_latest_reply(full_body)

        # Fetch metadata for headers
        meta: dict[str, Any] = (
            self._service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Message-ID", "From", "Subject"],
            )
            .execute()
        )

        headers = {h["name"]: h["value"] for h in meta["payload"]["headers"]}

        # Convert internalDate (ms since epoch) to ISO 8601
        internal_date_ms = int(msg.get("internalDate", "0"))
        received_at = datetime.fromtimestamp(internal_date_ms / 1000, tz=UTC).isoformat()

        return InboundEmail(
            gmail_message_id=message_id,
            thread_id=msg.get("threadId", ""),
            message_id_header=headers.get("Message-ID", ""),
            from_email=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            body_text=reply_text,
            received_at=received_at,
        )
