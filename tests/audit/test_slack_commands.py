"""Tests for Slack /audit command handler and Block Kit formatting."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from negotiation.audit.logger import AuditLogger
from negotiation.audit.slack_commands import (
    format_audit_blocks,
    parse_audit_query,
    register_audit_command,
)
from negotiation.audit.store import close_audit_db, init_audit_db


class TestParseAuditQuery:
    """Tests for Slack command text parsing."""

    def test_parses_influencer(self) -> None:
        result = parse_audit_query("influencer:Jane Doe")
        assert result == {"influencer": "Jane Doe"}

    def test_parses_campaign_and_last(self) -> None:
        result = parse_audit_query("campaign:camp_123 last:7d")
        assert result["campaign"] == "camp_123"
        assert result["last"] == "7d"

    def test_parses_event_type(self) -> None:
        result = parse_audit_query("event_type:escalation")
        assert result["event_type"] == "escalation"

    def test_handles_empty_input(self) -> None:
        result = parse_audit_query("")
        assert result == {}

    def test_handles_whitespace_only(self) -> None:
        result = parse_audit_query("   ")
        assert result == {}


class TestFormatAuditBlocks:
    """Tests for Block Kit output formatting."""

    def _make_entries(self, count: int) -> list[dict[str, Any]]:
        """Generate sample audit entries."""
        return [
            {
                "id": i + 1,
                "timestamp": f"2026-02-19T{10 + i:02d}:00:00Z",
                "event_type": "email_sent",
                "influencer_name": "Alice",
                "campaign_id": "camp_001",
                "negotiation_state": "outreach",
                "direction": "sent",
                "rates_used": "$500",
            }
            for i in range(count)
        ]

    def test_produces_blocks_with_header_and_results(self) -> None:
        results = self._make_entries(3)
        blocks = format_audit_blocks(results, {"influencer": "Alice"})

        # Header block
        assert blocks[0]["type"] == "header"
        assert "Alice" in blocks[0]["text"]["text"]

        # Count line
        assert blocks[1]["type"] == "section"
        assert "3 entries found" in blocks[1]["text"]["text"]

        # Should have section + divider for each entry
        section_blocks = [b for b in blocks if b["type"] == "section"]
        assert len(section_blocks) >= 4  # 1 count + 3 entries

    def test_truncates_to_10_with_overflow_note(self) -> None:
        results = self._make_entries(15)
        blocks = format_audit_blocks(results, {"influencer": "Alice", "last": "7d"})

        # Count line should show "showing most recent 10"
        count_block = blocks[1]
        assert "showing most recent 10" in count_block["text"]["text"]

        # Overflow footer
        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) == 1
        overflow_text = context_blocks[0]["elements"][0]["text"]
        assert "Showing 10 of 15 results" in overflow_text
        assert "Use CLI for full results" in overflow_text

        # Only 10 entry section blocks (not 15)
        entry_sections = [b for b in blocks if b["type"] == "section" and "fields" in b]
        assert len(entry_sections) == 10

    def test_empty_results(self) -> None:
        blocks = format_audit_blocks([], {"influencer": "Nobody"})
        count_block = blocks[1]
        assert "No entries found" in count_block["text"]["text"]


class TestRegisterAuditCommand:
    """Tests for command registration on Bolt app."""

    def test_registers_audit_command(self, tmp_path: Path) -> None:
        conn = init_audit_db(tmp_path / "audit.db")
        mock_app = MagicMock()
        register_audit_command(mock_app, conn)

        # The @app.command("/audit") decorator should have been called
        mock_app.command.assert_called_once_with("/audit")
        close_audit_db(conn)

    def test_handler_calls_ack_and_respond(self, tmp_path: Path) -> None:
        conn = init_audit_db(tmp_path / "audit.db")

        # Insert some test data
        logger = AuditLogger(conn)
        logger.log_email_sent("camp_1", "Alice", "t1", "body", "outreach")

        # Capture the registered handler
        mock_app = MagicMock()
        handler_fn: Any = None

        def capture_command(cmd: str):
            def decorator(fn: Any) -> Any:
                nonlocal handler_fn
                handler_fn = fn
                return fn

            return decorator

        mock_app.command = capture_command
        register_audit_command(mock_app, conn)

        # Call the handler
        ack = MagicMock()
        respond = MagicMock()
        command = {"text": "influencer:Alice"}

        assert handler_fn is not None
        handler_fn(ack=ack, command=command, respond=respond)

        ack.assert_called_once()
        respond.assert_called_once()
        # respond should have been called with blocks kwarg
        _, kwargs = respond.call_args
        assert "blocks" in kwargs
        close_audit_db(conn)
