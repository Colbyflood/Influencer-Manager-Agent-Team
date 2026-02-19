"""Tests for audit wiring module -- wrapper functions that add logging to pipeline operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from negotiation.audit.logger import AuditLogger
from negotiation.audit.store import close_audit_db, init_audit_db, query_audit_trail
from negotiation.audit.wiring import (
    create_audited_email_receive,
    create_audited_email_send,
    create_audited_process_reply,
    wire_audit_to_campaign_ingestion,
    wire_audit_to_dispatcher,
)


def _make_logger(tmp_path: Path) -> tuple[AuditLogger, Any]:
    """Create an AuditLogger with a fresh database."""
    conn = init_audit_db(tmp_path / "audit.db")
    logger = AuditLogger(conn)
    return logger, conn


class TestCreateAuditedEmailSend:
    """Tests for create_audited_email_send wrapper."""

    def test_calls_original_and_inserts_audit_entry(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        original = MagicMock(return_value="sent_ok")

        wrapped = create_audited_email_send(original, audit_logger)
        result = wrapped(
            influencer_name="Alice",
            thread_id="t_001",
            email_body="Hello Alice",
            negotiation_state="initial_outreach",
            rates_used="$500",
            campaign_id="camp_1",
        )

        assert result == "sent_ok"
        original.assert_called_once()

        entries = query_audit_trail(conn, influencer_name="Alice")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "email_sent"
        assert entries[0]["direction"] == "sent"
        assert entries[0]["email_body"] == "Hello Alice"
        assert entries[0]["rates_used"] == "$500"
        close_audit_db(conn)

    def test_passes_through_return_value(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        sentinel = {"status": "delivered", "id": 42}
        original = MagicMock(return_value=sentinel)

        wrapped = create_audited_email_send(original, audit_logger)
        result = wrapped(
            influencer_name="Bob",
            thread_id="t_002",
            email_body="Hi Bob",
            negotiation_state="counter_sent",
        )

        assert result is sentinel
        close_audit_db(conn)


class TestCreateAuditedEmailReceive:
    """Tests for create_audited_email_receive wrapper."""

    def test_calls_original_and_inserts_audit_entry_with_intent(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        original = MagicMock(return_value="received_ok")

        wrapped = create_audited_email_receive(original, audit_logger)
        result = wrapped(
            influencer_name="Charlie",
            thread_id="t_003",
            email_body="My rate is $1000",
            negotiation_state="counter_received",
            intent_classification="counter_offer",
            campaign_id="camp_2",
        )

        assert result == "received_ok"
        original.assert_called_once()

        entries = query_audit_trail(conn, influencer_name="Charlie")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "email_received"
        assert entries[0]["direction"] == "received"
        assert entries[0]["intent_classification"] == "counter_offer"
        close_audit_db(conn)

    def test_passes_through_return_value(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        sentinel = {"parsed": True}
        original = MagicMock(return_value=sentinel)

        wrapped = create_audited_email_receive(original, audit_logger)
        result = wrapped(
            influencer_name="Diana",
            thread_id="t_004",
            email_body="Thanks for reaching out",
            negotiation_state="initial_outreach",
        )

        assert result is sentinel
        close_audit_db(conn)


class TestCreateAuditedProcessReply:
    """Tests for create_audited_process_reply wrapper."""

    def test_action_send_logs_email_sent(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        original = MagicMock(
            return_value={
                "action": "send",
                "email_body": "Counter offer text",
                "our_rate": "$600",
            }
        )

        wrapped = create_audited_process_reply(original, audit_logger)
        ctx = {
            "campaign_id": "camp_3",
            "influencer_name": "Eve",
            "thread_id": "t_005",
            "negotiation_state": "counter_sent",
        }
        result = wrapped("email body", negotiation_context=ctx)

        assert result["action"] == "send"
        original.assert_called_once()

        entries = query_audit_trail(conn, influencer_name="Eve")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "email_sent"
        assert entries[0]["rates_used"] == "$600"
        close_audit_db(conn)

    def test_action_escalate_logs_escalation(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        original = MagicMock(return_value={"action": "escalate", "reason": "CPM too high"})

        wrapped = create_audited_process_reply(original, audit_logger)
        ctx = {
            "campaign_id": "camp_4",
            "influencer_name": "Frank",
            "thread_id": "t_006",
            "negotiation_state": "escalated",
        }
        result = wrapped("email body", negotiation_context=ctx)

        assert result["action"] == "escalate"

        entries = query_audit_trail(conn, influencer_name="Frank")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "escalation"
        assert entries[0]["metadata"]["reason"] == "CPM too high"
        close_audit_db(conn)

    def test_action_accept_logs_agreement(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        classification = MagicMock()
        classification.proposed_rate = "750"
        original = MagicMock(return_value={"action": "accept", "classification": classification})

        wrapped = create_audited_process_reply(original, audit_logger)
        ctx = {
            "campaign_id": "camp_5",
            "influencer_name": "Grace",
            "thread_id": "t_007",
            "negotiation_state": "agreed",
        }
        result = wrapped("email body", negotiation_context=ctx)

        assert result["action"] == "accept"

        entries = query_audit_trail(conn, influencer_name="Grace")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "agreement"
        assert entries[0]["rates_used"] == "750"
        close_audit_db(conn)

    def test_action_reject_logs_state_transition(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        original = MagicMock(return_value={"action": "reject"})

        wrapped = create_audited_process_reply(original, audit_logger)
        ctx = {
            "campaign_id": "camp_6",
            "influencer_name": "Hank",
            "thread_id": "t_008",
            "negotiation_state": "counter_received",
        }
        result = wrapped("email body", negotiation_context=ctx)

        assert result["action"] == "reject"

        entries = query_audit_trail(conn, influencer_name="Hank")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "state_transition"
        meta = entries[0]["metadata"]
        assert meta["from_state"] == "counter_received"
        assert meta["to_state"] == "rejected"
        close_audit_db(conn)

    def test_passes_through_return_value_unchanged(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        sentinel = {"action": "send", "email_body": "text", "extra_field": 42}
        original = MagicMock(return_value=sentinel)

        wrapped = create_audited_process_reply(original, audit_logger)
        ctx = {"influencer_name": "Ivy", "thread_id": "t_009", "negotiation_state": "s"}
        result = wrapped("email body", negotiation_context=ctx)

        assert result is sentinel
        assert result["extra_field"] == 42
        close_audit_db(conn)

    def test_extracts_context_from_positional_args(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        original = MagicMock(return_value={"action": "escalate", "reason": "test"})

        wrapped = create_audited_process_reply(original, audit_logger)
        ctx = {"influencer_name": "Jack", "thread_id": "t_010", "negotiation_state": "s"}
        result = wrapped("email body", ctx)

        assert result["action"] == "escalate"

        entries = query_audit_trail(conn, influencer_name="Jack")
        assert len(entries) == 1
        close_audit_db(conn)


class TestWireAuditToCampaignIngestion:
    """Tests for wire_audit_to_campaign_ingestion wrapper."""

    def test_logs_campaign_start_with_correct_counts(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        campaign_mock = MagicMock()
        campaign_mock.campaign_id = "camp_10"

        async def mock_ingest(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "campaign": campaign_mock,
                "found_influencers": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
                "missing_influencers": ["D", "E"],
            }

        wrapped = wire_audit_to_campaign_ingestion(mock_ingest, audit_logger)
        result = asyncio.run(wrapped("task_10", "token"))

        assert result["campaign"] is campaign_mock
        assert len(result["found_influencers"]) == 3

        entries = query_audit_trail(conn, campaign_id="camp_10")
        campaign_starts = [e for e in entries if e["event_type"] == "campaign_start"]
        assert len(campaign_starts) == 1
        meta = campaign_starts[0]["metadata"]
        assert meta["influencer_count"] == "5"
        assert meta["found_count"] == "3"
        assert meta["missing_count"] == "2"
        close_audit_db(conn)

    def test_logs_skip_for_each_missing_influencer(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        campaign_mock = MagicMock()
        campaign_mock.campaign_id = "camp_11"

        async def mock_ingest(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "campaign": campaign_mock,
                "found_influencers": [],
                "missing_influencers": ["Missing1", "Missing2", "Missing3"],
            }

        wrapped = wire_audit_to_campaign_ingestion(mock_ingest, audit_logger)
        asyncio.run(wrapped("task_11", "token"))

        entries = query_audit_trail(conn, campaign_id="camp_11")
        skips = [e for e in entries if e["event_type"] == "campaign_influencer_skip"]
        assert len(skips) == 3

        skip_names = {e["influencer_name"] for e in skips}
        assert skip_names == {"Missing1", "Missing2", "Missing3"}
        close_audit_db(conn)

    def test_passes_through_original_result_unchanged(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        campaign_mock = MagicMock()
        campaign_mock.campaign_id = "camp_12"
        sentinel = {
            "campaign": campaign_mock,
            "found_influencers": [{"name": "A"}],
            "missing_influencers": [],
            "extra": "preserved",
        }

        async def mock_ingest(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return sentinel

        wrapped = wire_audit_to_campaign_ingestion(mock_ingest, audit_logger)
        result = asyncio.run(wrapped("task_12", "token"))

        assert result is sentinel
        assert result["extra"] == "preserved"
        close_audit_db(conn)


class TestWireAuditToDispatcher:
    """Tests for wire_audit_to_dispatcher monkey-patching."""

    def test_dispatch_escalation_logs_escalation(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        dispatcher = MagicMock()
        dispatcher.dispatch_escalation.return_value = "ts_001"
        dispatcher.dispatch_agreement.return_value = "ts_002"
        dispatcher.pre_check.return_value = None

        wire_audit_to_dispatcher(dispatcher, audit_logger)

        payload = MagicMock()
        payload.campaign_id = None
        payload.influencer_name = "Luna"
        payload.thread_id = "t_100"
        payload.reason = "Budget exceeded"

        result = dispatcher.dispatch_escalation(payload)
        assert result == "ts_001"

        entries = query_audit_trail(conn, influencer_name="Luna")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "escalation"
        assert entries[0]["metadata"]["reason"] == "Budget exceeded"
        close_audit_db(conn)

    def test_dispatch_agreement_logs_agreement(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        dispatcher = MagicMock()
        dispatcher.dispatch_escalation.return_value = "ts_001"
        dispatcher.dispatch_agreement.return_value = "ts_003"
        dispatcher.pre_check.return_value = None

        wire_audit_to_dispatcher(dispatcher, audit_logger)

        payload = MagicMock()
        payload.campaign_id = None
        payload.influencer_name = "Mars"
        payload.thread_id = "t_200"
        payload.agreed_rate = "$900"

        result = dispatcher.dispatch_agreement(payload)
        assert result == "ts_003"

        entries = query_audit_trail(conn, influencer_name="Mars")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "agreement"
        assert entries[0]["rates_used"] == "$900"
        close_audit_db(conn)

    def test_pre_check_logs_takeover_on_human_skip(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        dispatcher = MagicMock()
        dispatcher.dispatch_escalation.return_value = "ts_001"
        dispatcher.dispatch_agreement.return_value = "ts_002"
        dispatcher.pre_check.return_value = {
            "action": "skip",
            "reason": "Thread is human-managed",
        }

        wire_audit_to_dispatcher(dispatcher, audit_logger)

        result = dispatcher.pre_check(
            email_body="test",
            thread_id="t_300",
        )
        assert result["action"] == "skip"

        entries = query_audit_trail(conn, limit=10)
        takeovers = [e for e in entries if e["event_type"] == "takeover"]
        assert len(takeovers) == 1
        assert takeovers[0]["thread_id"] == "t_300"
        close_audit_db(conn)

    def test_pre_check_no_log_when_no_skip(self, tmp_path: Path) -> None:
        audit_logger, conn = _make_logger(tmp_path)
        dispatcher = MagicMock()
        dispatcher.dispatch_escalation.return_value = "ts_001"
        dispatcher.dispatch_agreement.return_value = "ts_002"
        dispatcher.pre_check.return_value = None

        wire_audit_to_dispatcher(dispatcher, audit_logger)

        result = dispatcher.pre_check(email_body="test", thread_id="t_400")
        assert result is None

        entries = query_audit_trail(conn, limit=10)
        assert len(entries) == 0
        close_audit_db(conn)
