"""Tests for AuditLogger convenience methods covering all 9 event types."""

from pathlib import Path

from negotiation.audit.logger import AuditLogger
from negotiation.audit.store import close_audit_db, init_audit_db, query_audit_trail


class TestAuditLogger:
    """Tests for AuditLogger convenience methods."""

    def _make_logger(self, tmp_path: Path) -> tuple[AuditLogger, object]:
        """Create an AuditLogger with a fresh database."""
        conn = init_audit_db(tmp_path / "audit.db")
        logger = AuditLogger(conn)
        return logger, conn

    def test_log_email_sent(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_email_sent(
            campaign_id="camp_001",
            influencer_name="Alice",
            thread_id="thread_abc",
            email_body="Hi Alice, we'd like to collaborate...",
            negotiation_state="initial_outreach",
            rates_used="$500",
            metadata={"template": "outreach_v2"},
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Alice")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "email_sent"
        assert results[0]["direction"] == "sent"
        assert results[0]["email_body"] == "Hi Alice, we'd like to collaborate..."
        assert results[0]["negotiation_state"] == "initial_outreach"
        assert results[0]["rates_used"] == "$500"
        assert results[0]["metadata"]["template"] == "outreach_v2"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_email_received(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_email_received(
            campaign_id="camp_001",
            influencer_name="Bob",
            thread_id="thread_def",
            email_body="Thanks, my rate is $1000...",
            negotiation_state="counter_received",
            intent_classification="counter_offer",
            rates_used="$1000",
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Bob")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "email_received"
        assert results[0]["direction"] == "received"
        assert results[0]["intent_classification"] == "counter_offer"
        assert results[0]["rates_used"] == "$1000"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_state_transition(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_state_transition(
            campaign_id="camp_002",
            influencer_name="Charlie",
            thread_id="thread_ghi",
            from_state="initial_outreach",
            to_state="counter_received",
            event="receive_reply",
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Charlie")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "state_transition"
        meta = results[0]["metadata"]
        assert meta["from_state"] == "initial_outreach"
        assert meta["to_state"] == "counter_received"
        assert meta["event"] == "receive_reply"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_escalation(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_escalation(
            campaign_id="camp_003",
            influencer_name="Diana",
            thread_id="thread_jkl",
            reason="Rate exceeds max budget",
            negotiation_state="escalated",
            rates_used="$2000",
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Diana")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "escalation"
        assert results[0]["metadata"]["reason"] == "Rate exceeds max budget"
        assert results[0]["negotiation_state"] == "escalated"
        assert results[0]["rates_used"] == "$2000"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_agreement(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_agreement(
            campaign_id="camp_004",
            influencer_name="Eve",
            thread_id="thread_mno",
            agreed_rate="$750",
            negotiation_state="agreed",
            metadata={"deliverables": "2 posts, 1 story"},
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Eve")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "agreement"
        assert results[0]["rates_used"] == "$750"
        assert results[0]["metadata"]["deliverables"] == "2 posts, 1 story"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_takeover(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_takeover(
            campaign_id="camp_005",
            influencer_name="Frank",
            thread_id="thread_pqr",
            taken_by="U12345",
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Frank")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "takeover"
        assert results[0]["metadata"]["taken_by"] == "U12345"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_campaign_start(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_campaign_start(
            campaign_id="camp_006",
            influencer_count=20,
            found_count=18,
            missing_count=2,
        )
        assert row_id > 0
        results = query_audit_trail(conn, campaign_id="camp_006")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "campaign_start"
        meta = results[0]["metadata"]
        assert meta["influencer_count"] == "20"
        assert meta["found_count"] == "18"
        assert meta["missing_count"] == "2"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_campaign_influencer_skip(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_campaign_influencer_skip(
            campaign_id="camp_007",
            influencer_name="Grace",
            reason="Not found in database",
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Grace")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "campaign_influencer_skip"
        assert results[0]["metadata"]["reason"] == "Not found in database"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_error(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_error(
            campaign_id="camp_008",
            influencer_name="Hank",
            error_message="Connection timeout",
            context="Gmail API call",
        )
        assert row_id > 0
        results = query_audit_trail(conn, influencer_name="Hank")  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["event_type"] == "error"
        meta = results[0]["metadata"]
        assert meta["error_message"] == "Connection timeout"
        assert meta["context"] == "Gmail API call"
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_log_error_without_context(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        row_id = logger.log_error(
            campaign_id=None,
            influencer_name=None,
            error_message="Unexpected failure",
        )
        assert row_id > 0
        results = query_audit_trail(conn, limit=1)  # type: ignore[arg-type]
        assert len(results) == 1
        assert results[0]["metadata"]["error_message"] == "Unexpected failure"
        assert "context" not in results[0]["metadata"]
        close_audit_db(conn)  # type: ignore[arg-type]

    def test_all_methods_return_valid_row_id(self, tmp_path: Path) -> None:
        logger, conn = self._make_logger(tmp_path)
        ids = [
            logger.log_email_sent("c", "a", "t", "body", "state"),
            logger.log_email_received("c", "a", "t", "body", "state"),
            logger.log_state_transition("c", "a", "t", "s1", "s2", "e"),
            logger.log_escalation("c", "a", "t", "reason", "state"),
            logger.log_agreement("c", "a", "t", "$500", "agreed"),
            logger.log_takeover("c", "a", "t", "U123"),
            logger.log_campaign_start("c", 10, 8, 2),
            logger.log_campaign_influencer_skip("c", "a", "reason"),
            logger.log_error("c", "a", "msg"),
        ]
        for row_id in ids:
            assert row_id > 0
        # All 9 entries inserted
        results = query_audit_trail(conn, limit=100)  # type: ignore[arg-type]
        assert len(results) == 9
        close_audit_db(conn)  # type: ignore[arg-type]
