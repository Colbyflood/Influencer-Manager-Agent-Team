"""Email thread context extraction and reply header management.

Provides helpers for:
- Extracting threading metadata from Gmail API thread responses
- Building RFC 2822 reply headers for threaded email replies
"""

from __future__ import annotations

from typing import Any

from negotiation.email.models import EmailThreadContext


def get_thread_context(service: Any, thread_id: str) -> EmailThreadContext:
    """Extract threading context from the latest message in a Gmail thread.

    Calls the Gmail API ``threads.get`` endpoint with ``format="metadata"``
    to retrieve only header information (no body content).  Extracts the
    ``Message-ID``, ``Subject``, and ``From`` headers from the last message
    in the thread.

    Args:
        service: An authenticated Gmail API service resource.
        thread_id: The Gmail thread ID to look up.

    Returns:
        An ``EmailThreadContext`` with the thread's ID, last message's
        Message-ID header, subject line, and sender email address.
    """
    thread = (
        service.users()
        .threads()
        .get(
            userId="me",
            id=thread_id,
            format="metadata",
            metadataHeaders=["Message-ID", "Subject", "From"],
        )
        .execute()
    )

    latest_msg = thread["messages"][-1]
    headers = {h["name"]: h["value"] for h in latest_msg["payload"]["headers"]}

    return EmailThreadContext(
        thread_id=thread_id,
        last_message_id=headers.get("Message-ID", ""),
        subject=headers.get("Subject", ""),
        influencer_email=headers.get("From", ""),
    )


def build_reply_headers(thread_ctx: EmailThreadContext) -> dict[str, str]:
    """Build RFC 2822 reply headers from an existing thread context.

    Generates the ``In-Reply-To``, ``References``, ``Subject``, and ``To``
    headers needed to send a properly threaded reply.  The ``Subject`` is
    prefixed with ``Re: `` only if not already present (case-insensitive).

    Args:
        thread_ctx: The thread context from ``get_thread_context``.

    Returns:
        A dict of header names to values suitable for setting on an
        ``email.message.EmailMessage``.
    """
    subject = thread_ctx.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    return {
        "In-Reply-To": thread_ctx.last_message_id,
        "References": thread_ctx.last_message_id,
        "Subject": subject,
        "To": thread_ctx.influencer_email,
    }
