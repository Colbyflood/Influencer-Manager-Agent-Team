"""Email domain: Gmail API client, threading, parsing, and models."""

from negotiation.email.client import GmailClient
from negotiation.email.models import (
    EmailThreadContext,
    InboundEmail,
    OutboundEmail,
)
from negotiation.email.parser import extract_latest_reply, parse_mime_message
from negotiation.email.threading import build_reply_headers, get_thread_context

__all__ = [
    "EmailThreadContext",
    "GmailClient",
    "InboundEmail",
    "OutboundEmail",
    "build_reply_headers",
    "extract_latest_reply",
    "get_thread_context",
    "parse_mime_message",
]
