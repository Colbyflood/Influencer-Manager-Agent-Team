"""Tests for the CLI query interface for the audit trail."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from negotiation.audit.cli import (
    build_parser,
    format_json,
    format_table,
    main,
    parse_last_duration,
)
from negotiation.audit.logger import AuditLogger
from negotiation.audit.store import close_audit_db, init_audit_db


class TestBuildParser:
    """Tests for argument parser construction."""

    def test_accepts_all_arguments(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--influencer",
            "Jane Doe",
            "--campaign",
            "camp_123",
            "--from-date",
            "2026-01-01",
            "--to-date",
            "2026-02-01",
            "--event-type",
            "email_sent",
            "--last",
            "7d",
            "--format",
            "json",
            "--limit",
            "100",
            "--db",
            "/tmp/test.db",
        ])
        assert args.influencer == "Jane Doe"
        assert args.campaign == "camp_123"
        assert args.from_date == "2026-01-01"
        assert args.to_date == "2026-02-01"
        assert args.event_type == "email_sent"
        assert args.last == "7d"
        assert args.output_format == "json"
        assert args.limit == 100
        assert args.db == "/tmp/test.db"

    def test_default_values(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.influencer is None
        assert args.campaign is None
        assert args.output_format == "table"
        assert args.limit == 50


class TestParseLastDuration:
    """Tests for parse_last_duration conversion."""

    def test_converts_7d_to_correct_date(self) -> None:
        result = parse_last_duration("7d")
        expected = datetime.now(tz=UTC) - timedelta(days=7)
        # Parse result and check it's within 2 seconds of expected
        result_dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        assert abs((result_dt - expected).total_seconds()) < 2

    def test_converts_24h_to_correct_date(self) -> None:
        result = parse_last_duration("24h")
        expected = datetime.now(tz=UTC) - timedelta(hours=24)
        result_dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        assert abs((result_dt - expected).total_seconds()) < 2

    def test_converts_30d_to_correct_date(self) -> None:
        result = parse_last_duration("30d")
        expected = datetime.now(tz=UTC) - timedelta(days=30)
        result_dt = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        assert abs((result_dt - expected).total_seconds()) < 2

    def test_raises_on_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized duration format"):
            parse_last_duration("7x")

    def test_raises_on_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized duration format"):
            parse_last_duration("")


class TestFormatTable:
    """Tests for table output formatting."""

    def test_produces_readable_output_with_header(self) -> None:
        results = [
            {
                "timestamp": "2026-02-19T10:00:00Z",
                "event_type": "email_sent",
                "influencer_name": "Alice",
                "campaign_id": "camp_001",
                "negotiation_state": "initial_outreach",
                "direction": "sent",
            },
        ]
        output = format_table(results)
        assert "Timestamp" in output
        assert "Event" in output
        assert "Alice" in output
        assert "email_sent" in output
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + separator + 1 row

    def test_empty_results(self) -> None:
        output = format_table([])
        assert output == "No results found."


class TestFormatJson:
    """Tests for JSON output formatting."""

    def test_produces_valid_json(self) -> None:
        results = [{"event_type": "email_sent", "influencer_name": "Alice"}]
        output = format_json(results)
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["event_type"] == "email_sent"


class TestMain:
    """Tests for the main() entry point."""

    def test_main_with_influencer_flag(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        conn = init_audit_db(db_path)
        logger = AuditLogger(conn)
        logger.log_email_sent("camp_1", "Jane Doe", "t1", "body", "outreach")
        logger.log_email_sent("camp_2", "Other", "t2", "body", "outreach")
        close_audit_db(conn)

        with patch(
            "sys.argv",
            ["cli", "--influencer", "Jane Doe", "--db", str(db_path)],
        ):
            main()
        # If main() completes without error, query was successful
