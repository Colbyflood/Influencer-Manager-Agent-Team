"""MIME email parsing and reply text extraction.

Provides helpers for:
- Decoding raw email bytes into plain text body content
- Extracting only the latest reply from a multi-message email thread
"""

from __future__ import annotations

import re
from email import message_from_bytes
from email.message import Message

from mailparser_reply import EmailReplyParser  # type: ignore[import-untyped]


def parse_mime_message(raw_bytes: bytes) -> str:
    """Parse raw email bytes and extract the text body.

    Decodes an RFC 2822 MIME message from raw bytes (as returned by the
    Gmail API after base64url decoding).  Extracts the ``text/plain`` body
    part.  For multipart messages, walks all parts to find ``text/plain``.
    If no ``text/plain`` part exists, falls back to ``text/html`` with HTML
    tags stripped via regex.

    Args:
        raw_bytes: The raw email bytes (already base64url-decoded).

    Returns:
        The decoded text body of the email.  Returns an empty string if
        no text content could be extracted.
    """
    msg: Message = message_from_bytes(raw_bytes)

    if msg.is_multipart():
        text_plain = ""
        text_html = ""
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not text_plain:
                raw_payload = part.get_payload(decode=True)
                if isinstance(raw_payload, bytes) and raw_payload:
                    text_plain = raw_payload.decode("utf-8", errors="replace")
            elif content_type == "text/html" and not text_html:
                raw_payload = part.get_payload(decode=True)
                if isinstance(raw_payload, bytes) and raw_payload:
                    text_html = raw_payload.decode("utf-8", errors="replace")

        if text_plain:
            return text_plain
        if text_html:
            return re.sub(r"<[^>]+>", "", text_html)
        return ""

    # Non-multipart message
    raw_payload = msg.get_payload(decode=True)
    if isinstance(raw_payload, bytes) and raw_payload:
        content_type = msg.get_content_type()
        text = raw_payload.decode("utf-8", errors="replace")
        if content_type == "text/html":
            return re.sub(r"<[^>]+>", "", text)
        return text

    return ""


def extract_latest_reply(full_body: str) -> str:
    """Extract only the latest reply text from an email thread body.

    Uses ``mail-parser-reply`` to strip quoted content, signature blocks,
    and forwarded message headers, returning only the new content from the
    most recent reply.

    If the parser returns an empty string (e.g. the entire message was
    detected as quoted content), the original ``full_body`` is returned
    as a fallback.

    Args:
        full_body: The full text body of the email (may contain quoted
            replies, signatures, etc.).

    Returns:
        The extracted latest reply text, or the original body if
        extraction yields nothing.
    """
    parsed: str = EmailReplyParser(languages=["en"]).parse_reply(text=full_body)
    if not parsed or not parsed.strip():
        return full_body
    return parsed
