"""Unit tests for GmailWatchStore persistence layer.

Tests cover: save/load cycle, empty state, singleton enforcement, and
updated_at timestamp changes on re-save.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from negotiation.state.schema import init_gmail_watch_state_table
from negotiation.state.watch_store import GmailWatchStore


@pytest.fixture()
def watch_store() -> GmailWatchStore:
    """Create an in-memory GmailWatchStore with the schema initialized."""
    conn = sqlite3.connect(":memory:")
    init_gmail_watch_state_table(conn)
    return GmailWatchStore(conn)


class TestGmailWatchStore:
    """Tests for GmailWatchStore save and load operations."""

    def test_save_and_load(self, watch_store: GmailWatchStore) -> None:
        """Save expiration and history_id, then load them back."""
        watch_store.save(expiration_ms=1700000000000, history_id="abc123")
        result = watch_store.load()
        assert result is not None
        assert result == (1700000000000, "abc123")

    def test_load_returns_none_when_empty(self, watch_store: GmailWatchStore) -> None:
        """Fresh store with no saved data returns None."""
        result = watch_store.load()
        assert result is None

    def test_save_overwrites_singleton(self, watch_store: GmailWatchStore) -> None:
        """Saving twice overwrites the first value; only one row exists."""
        watch_store.save(expiration_ms=1000, history_id="first")
        watch_store.save(expiration_ms=2000, history_id="second")

        result = watch_store.load()
        assert result is not None
        assert result == (2000, "second")

        # Verify only one row exists
        row_count = watch_store._conn.execute("SELECT COUNT(*) FROM gmail_watch_state").fetchone()[
            0
        ]
        assert row_count == 1

    def test_save_updates_updated_at(self, watch_store: GmailWatchStore) -> None:
        """Consecutive saves produce different updated_at timestamps."""
        t1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC)

        with patch("negotiation.state.watch_store.datetime") as mock_dt:
            mock_dt.now.return_value = t1
            watch_store.save(expiration_ms=1000, history_id="first")

        first_ts = watch_store._conn.execute(
            "SELECT updated_at FROM gmail_watch_state WHERE id = 1"
        ).fetchone()[0]

        with patch("negotiation.state.watch_store.datetime") as mock_dt:
            mock_dt.now.return_value = t2
            watch_store.save(expiration_ms=2000, history_id="second")

        second_ts = watch_store._conn.execute(
            "SELECT updated_at FROM gmail_watch_state WHERE id = 1"
        ).fetchone()[0]

        assert second_ts != first_ts
        assert first_ts == "2026-01-01T12:00:00Z"
        assert second_ts == "2026-01-01T13:00:00Z"
