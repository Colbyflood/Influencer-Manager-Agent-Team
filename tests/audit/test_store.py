"""Tests for SQLite audit store: init, insert, query, and SQL injection prevention."""

import time
from pathlib import Path

from negotiation.audit.models import AuditEntry, EventType
from negotiation.audit.store import (
    close_audit_db,
    init_audit_db,
    insert_audit_entry,
    query_audit_trail,
)


class TestInitAuditDB:
    """Tests for database initialization."""

    def test_creates_database_file(self, tmp_path: Path):
        db_path = tmp_path / "audit.db"
        conn = init_audit_db(db_path)
        assert db_path.exists()
        close_audit_db(conn)

    def test_wal_mode_enabled(self, tmp_path: Path):
        db_path = tmp_path / "audit.db"
        conn = init_audit_db(db_path)
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal"
        close_audit_db(conn)

    def test_audit_log_table_exists(self, tmp_path: Path):
        db_path = tmp_path / "audit.db"
        conn = init_audit_db(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
        )
        assert cursor.fetchone() is not None
        close_audit_db(conn)

    def test_indexes_created(self, tmp_path: Path):
        db_path = tmp_path / "audit.db"
        conn = init_audit_db(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_audit_%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_audit_influencer" in indexes
        assert "idx_audit_campaign" in indexes
        assert "idx_audit_timestamp" in indexes
        close_audit_db(conn)


class TestInsertAuditEntry:
    """Tests for inserting audit entries."""

    def test_insert_returns_row_id(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        entry = AuditEntry(
            event_type=EventType.EMAIL_SENT,
            campaign_id="camp_001",
            influencer_name="Alice",
        )
        row_id = insert_audit_entry(conn, entry)
        assert row_id >= 1
        close_audit_db(conn)

    def test_insert_stores_all_fields(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        entry = AuditEntry(
            event_type=EventType.STATE_TRANSITION,
            campaign_id="camp_002",
            influencer_name="Bob",
            thread_id="thread_abc",
            direction="inbound",
            email_body="Test email body",
            negotiation_state="counter_received",
            rates_used="$25 CPM",
            intent_classification="counter_offer",
            metadata={"key": "value"},
        )
        insert_audit_entry(conn, entry)

        results = query_audit_trail(conn, influencer_name="Bob")
        assert len(results) == 1
        row = results[0]
        assert row["event_type"] == "state_transition"
        assert row["campaign_id"] == "camp_002"
        assert row["influencer_name"] == "Bob"
        assert row["thread_id"] == "thread_abc"
        assert row["direction"] == "inbound"
        assert row["email_body"] == "Test email body"
        assert row["negotiation_state"] == "counter_received"
        assert row["rates_used"] == "$25 CPM"
        assert row["intent_classification"] == "counter_offer"
        assert row["metadata"] == {"key": "value"}
        close_audit_db(conn)


class TestQueryAuditTrail:
    """Tests for querying the audit trail with various filters."""

    def _seed_entries(self, conn, count: int = 5):
        """Insert multiple entries for query testing."""
        entries = [
            AuditEntry(
                event_type=EventType.EMAIL_SENT,
                campaign_id="camp_A",
                influencer_name="Alice",
            ),
            AuditEntry(
                event_type=EventType.EMAIL_RECEIVED,
                campaign_id="camp_A",
                influencer_name="Bob",
            ),
            AuditEntry(
                event_type=EventType.ESCALATION,
                campaign_id="camp_B",
                influencer_name="Alice",
            ),
            AuditEntry(
                event_type=EventType.AGREEMENT,
                campaign_id="camp_B",
                influencer_name="Charlie",
            ),
            AuditEntry(
                event_type=EventType.ERROR,
                campaign_id="camp_A",
                influencer_name="Alice",
            ),
        ]
        for entry in entries[:count]:
            insert_audit_entry(conn, entry)
            # Small sleep to ensure distinct timestamps
            time.sleep(0.01)

    def test_filter_by_influencer_name(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        results = query_audit_trail(conn, influencer_name="Alice")
        assert len(results) == 3
        for row in results:
            assert row["influencer_name"] == "Alice"
        close_audit_db(conn)

    def test_filter_by_campaign_id(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        results = query_audit_trail(conn, campaign_id="camp_B")
        assert len(results) == 2
        for row in results:
            assert row["campaign_id"] == "camp_B"
        close_audit_db(conn)

    def test_filter_by_event_type(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        results = query_audit_trail(conn, event_type="email_sent")
        assert len(results) == 1
        assert results[0]["event_type"] == "email_sent"
        close_audit_db(conn)

    def test_filter_by_date_range(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        # Get all entries to find date range
        all_entries = query_audit_trail(conn, limit=100)
        assert len(all_entries) >= 2

        # Use a date range that captures all entries
        first_ts = all_entries[-1]["timestamp"]
        last_ts = all_entries[0]["timestamp"]
        results = query_audit_trail(conn, from_date=first_ts, to_date=last_ts)
        assert len(results) == len(all_entries)
        close_audit_db(conn)

    def test_limit_parameter(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        results = query_audit_trail(conn, limit=2)
        assert len(results) == 2
        close_audit_db(conn)

    def test_results_ordered_by_timestamp_desc(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        results = query_audit_trail(conn, limit=100)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)
        close_audit_db(conn)

    def test_metadata_round_trip(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        entry = AuditEntry(
            event_type=EventType.CAMPAIGN_START,
            campaign_id="camp_meta",
            metadata={"source": "clickup", "form_id": "form_123"},
        )
        insert_audit_entry(conn, entry)

        results = query_audit_trail(conn, campaign_id="camp_meta")
        assert len(results) == 1
        assert results[0]["metadata"] == {"source": "clickup", "form_id": "form_123"}
        close_audit_db(conn)

    def test_sql_injection_prevention(self, tmp_path: Path):
        """Parameterized queries should safely handle SQL injection attempts."""
        conn = init_audit_db(tmp_path / "audit.db")
        malicious_name = "Alice'; DROP TABLE audit_log; --"
        entry = AuditEntry(
            event_type=EventType.EMAIL_SENT,
            influencer_name=malicious_name,
        )
        row_id = insert_audit_entry(conn, entry)
        assert row_id >= 1

        # Table should still exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
        )
        assert cursor.fetchone() is not None

        # Should be able to query by the malicious name
        results = query_audit_trail(conn, influencer_name=malicious_name)
        assert len(results) == 1
        assert results[0]["influencer_name"] == malicious_name
        close_audit_db(conn)

    def test_no_filters_returns_all(self, tmp_path: Path):
        conn = init_audit_db(tmp_path / "audit.db")
        self._seed_entries(conn)

        results = query_audit_trail(conn, limit=100)
        assert len(results) == 5
        close_audit_db(conn)
