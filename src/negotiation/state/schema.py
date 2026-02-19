"""SQLite schema for negotiation state persistence.

Provides the DDL function to create the negotiation_state table following the
same pattern as init_audit_db() in negotiation.audit.store.
"""

from __future__ import annotations

import sqlite3


def init_negotiation_state_table(conn: sqlite3.Connection) -> None:
    """Create the negotiation_state table if it does not already exist.

    Creates a table with columns for the full negotiation snapshot: state,
    round count, serialized context/campaign/CPM tracker/history, and
    timestamps.  Also creates an index on the state column for efficient
    ``load_active()`` queries.

    Args:
        conn: An open sqlite3.Connection (WAL mode recommended).
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS negotiation_state (
            thread_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            round_count INTEGER NOT NULL DEFAULT 0,
            context_json TEXT NOT NULL,
            campaign_json TEXT NOT NULL,
            cpm_tracker_json TEXT NOT NULL,
            history_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_neg_state_state ON negotiation_state (state)"
    )

    conn.commit()
