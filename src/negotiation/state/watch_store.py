"""SQLite-backed store for Gmail watch expiration persistence.

Persists the Gmail watch ``expiration`` timestamp and ``historyId`` so that
the renewal loop survives process restarts without missing the 7-day expiry
window.  Uses a singleton row pattern (``id = 1``) -- only one watch state
is tracked at a time.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class GmailWatchStore:
    """Persist and retrieve Gmail watch expiration data in SQLite.

    The underlying ``gmail_watch_state`` table enforces a single-row
    constraint via ``CHECK (id = 1)``.  ``save()`` upserts this singleton
    row; ``load()`` reads it back (or returns ``None`` on first run).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with an open database connection.

        Args:
            conn: An open sqlite3.Connection whose database already has the
                  ``gmail_watch_state`` table (see ``init_gmail_watch_state_table``).
        """
        self._conn = conn

    def save(self, expiration_ms: int, history_id: str) -> None:
        """Persist Gmail watch expiration and history ID (upsert singleton row).

        Args:
            expiration_ms: The watch expiration timestamp in milliseconds
                           (from Gmail API ``watch()`` response).
            history_id: The Gmail history ID at the time of watch setup.
        """
        now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._conn.execute(
            "INSERT OR REPLACE INTO gmail_watch_state "
            "(id, expiration_ms, history_id, updated_at) VALUES (1, ?, ?, ?)",
            (expiration_ms, history_id, now),
        )
        self._conn.commit()

    def load(self) -> tuple[int, str] | None:
        """Load persisted expiration_ms and history_id.

        Returns:
            A ``(expiration_ms, history_id)`` tuple, or ``None`` if no record
            exists (first run).
        """
        cursor = self._conn.execute(
            "SELECT expiration_ms, history_id FROM gmail_watch_state WHERE id = 1"
        )
        row = cursor.fetchone()
        return (row[0], row[1]) if row else None
