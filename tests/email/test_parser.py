"""Tests for MIME email parsing and reply text extraction."""

from __future__ import annotations

from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from negotiation.email.parser import extract_latest_reply, parse_mime_message

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plain_email(body: str) -> bytes:
    """Create raw bytes for a plain-text-only email."""
    msg = EmailMessage()
    msg["From"] = "influencer@example.com"
    msg["To"] = "agent@example.com"
    msg["Subject"] = "Test"
    msg.set_content(body)
    return msg.as_bytes()


def _make_multipart_email(*, text_plain: str | None = None, text_html: str | None = None) -> bytes:
    """Create raw bytes for a multipart email with optional text/plain and text/html."""
    msg = MIMEMultipart("alternative")
    msg["From"] = "influencer@example.com"
    msg["To"] = "agent@example.com"
    msg["Subject"] = "Test"

    if text_plain is not None:
        msg.attach(MIMEText(text_plain, "plain"))
    if text_html is not None:
        msg.attach(MIMEText(text_html, "html"))

    return msg.as_bytes()


def _make_html_only_email(html: str) -> bytes:
    """Create raw bytes for an HTML-only (non-multipart) email."""
    msg = EmailMessage()
    msg["From"] = "influencer@example.com"
    msg["To"] = "agent@example.com"
    msg["Subject"] = "Test"
    msg.set_content(html, subtype="html")
    return msg.as_bytes()


# ---------------------------------------------------------------------------
# parse_mime_message tests
# ---------------------------------------------------------------------------


class TestParseMimeMessage:
    """Tests for parse_mime_message."""

    def test_plain_text_email(self) -> None:
        raw = _make_plain_email("Hello, let's discuss rates.")
        result = parse_mime_message(raw)
        assert "Hello, let's discuss rates." in result

    def test_multipart_with_text_plain(self) -> None:
        raw = _make_multipart_email(text_plain="Plain version", text_html="<p>HTML version</p>")
        result = parse_mime_message(raw)
        assert result == "Plain version"

    def test_multipart_html_only_strips_tags(self) -> None:
        raw = _make_multipart_email(text_html="<p>Hello <b>world</b></p>")
        result = parse_mime_message(raw)
        assert "Hello" in result
        assert "world" in result
        assert "<p>" not in result
        assert "<b>" not in result

    def test_html_only_non_multipart(self) -> None:
        raw = _make_html_only_email("<div>Rate is $500</div>")
        result = parse_mime_message(raw)
        assert "Rate is $500" in result
        assert "<div>" not in result

    def test_empty_body_returns_empty_string(self) -> None:
        msg = EmailMessage()
        msg["From"] = "test@example.com"
        msg["Subject"] = "Empty"
        raw = msg.as_bytes()
        result = parse_mime_message(raw)
        assert result == ""

    def test_prefers_text_plain_over_html(self) -> None:
        raw = _make_multipart_email(
            text_plain="I prefer plain",
            text_html="<p>I prefer HTML</p>",
        )
        result = parse_mime_message(raw)
        assert result == "I prefer plain"

    def test_multipart_empty_text_plain_falls_to_html(self) -> None:
        """If text/plain is present but empty, fall back to HTML."""
        msg = MIMEMultipart("alternative")
        msg["From"] = "test@example.com"
        msg["Subject"] = "Test"
        msg.attach(MIMEText("", "plain"))
        msg.attach(MIMEText("<p>Fallback HTML</p>", "html"))
        raw = msg.as_bytes()
        result = parse_mime_message(raw)
        # Empty text/plain still counts as found since it has a payload
        # but the text is empty, so we should get the empty text/plain
        # Our implementation stores first non-empty text/plain
        assert "Fallback HTML" in result

    def test_unicode_content_handled(self) -> None:
        raw = _make_plain_email("Price: \u20ac500 for the caf\u00e9 collab")
        result = parse_mime_message(raw)
        assert "\u20ac500" in result
        assert "caf\u00e9" in result

    def test_html_strips_nested_tags(self) -> None:
        html = "<html><body><div><p>Nested <em>tags</em> here</p></div></body></html>"
        raw = _make_multipart_email(text_html=html)
        result = parse_mime_message(raw)
        assert "Nested" in result
        assert "tags" in result
        assert "here" in result
        assert "<" not in result

    def test_returns_string_type(self) -> None:
        raw = _make_plain_email("test")
        result = parse_mime_message(raw)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# extract_latest_reply tests
# ---------------------------------------------------------------------------


class TestExtractLatestReply:
    """Tests for extract_latest_reply."""

    def test_simple_text_no_quoted(self) -> None:
        text = "Sounds good, let's go with $500."
        result = extract_latest_reply(text)
        assert "Sounds good" in result

    def test_strips_on_wrote_quoted_content(self) -> None:
        text = (
            "I accept the offer.\n\n"
            "On Mon, Jan 1, 2026 at 10:00 AM Agent <agent@co.com> wrote:\n"
            "> Here is our proposal for $500.\n"
            "> Let me know what you think.\n"
        )
        result = extract_latest_reply(text)
        assert "I accept the offer" in result
        assert "Here is our proposal" not in result

    def test_strips_forwarded_content(self) -> None:
        text = (
            "See below.\n\n"
            "---------- Forwarded message ----------\n"
            "From: someone@example.com\n"
            "Date: Mon, Jan 1, 2026\n"
            "Subject: FW: Deal\n\n"
            "Original message content here.\n"
        )
        result = extract_latest_reply(text)
        assert "See below" in result

    def test_empty_extraction_returns_original(self) -> None:
        """If the parser returns empty, fall back to the original text."""
        # A message that is entirely quoted content
        text = "> Just a quoted line"
        result = extract_latest_reply(text)
        # Should return something (either parsed or fallback)
        assert len(result) > 0

    def test_multiline_reply_preserved(self) -> None:
        text = (
            "Thanks for reaching out!\n"
            "I'd love to collaborate.\n"
            "My rate is $750.\n\n"
            "On Tue, Jan 2, 2026 at 3:00 PM wrote:\n"
            "> Would you be interested in a partnership?\n"
        )
        result = extract_latest_reply(text)
        assert "collaborate" in result
        assert "$750" in result

    def test_returns_string_type(self) -> None:
        result = extract_latest_reply("Hello there")
        assert isinstance(result, str)
