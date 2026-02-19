"""SQLite-backed audit trail store with WAL mode and indexed queries.

Provides functions to initialize the database, insert audit entries, and
query the audit trail with flexible filtering. Uses parameterized queries
exclusively (never string concatenation) to prevent SQL injection.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from negotiation.audit.models import AuditEntry


def init_audit_db(db_path: Path) -> sqlite3.Connection:
    """Create and initialize the audit database with WAL mode and indexes.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        An open sqlite3.Connection with WAL mode enabled.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            event_type TEXT NOT NULL,
            campaign_id TEXT,
            influencer_name TEXT,
            thread_id TEXT,
            direction TEXT,
            email_body TEXT,
            negotiation_state TEXT,
            rates_used TEXT,
            intent_classification TEXT,
            metadata TEXT
        )
    """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_influencer ON audit_log (influencer_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_campaign ON audit_log (campaign_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp)"
    )

    conn.commit()
    return conn


def insert_audit_entry(conn: sqlite3.Connection, entry: AuditEntry) -> int:
    """Insert an audit entry into the database.

    Uses parameterized queries exclusively to prevent SQL injection.
    Serializes metadata dict to JSON string if present.

    Args:
        conn: An open database connection.
        entry: The audit entry to insert.

    Returns:
        The row ID of the inserted entry.
    """
    metadata_json: str | None = None
    if entry.metadata is not None:
        metadata_json = json.dumps(entry.metadata)

    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    cursor = conn.execute(
        """
        INSERT INTO audit_log (
            timestamp, event_type, campaign_id, influencer_name, thread_id,
            direction, email_body, negotiation_state, rates_used,
            intent_classification, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            entry.event_type.value,
            entry.campaign_id,
            entry.influencer_name,
            entry.thread_id,
            entry.direction,
            entry.email_body,
            entry.negotiation_state,
            entry.rates_used,
            entry.intent_classification,
            metadata_json,
        ),
    )
    conn.commit()
    return cursor.lastrowid or 0


def query_audit_trail(
    conn: sqlite3.Connection,
    *,
    influencer_name: str | None = None,
    campaign_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query the audit trail with flexible filtering.

    All filters are optional. Uses parameterized queries exclusively.
    Results are ordered by timestamp DESC.

    Args:
        conn: An open database connection.
        influencer_name: Filter by influencer name (exact match).
        campaign_id: Filter by campaign ID (exact match).
        from_date: Filter entries on or after this ISO 8601 date.
        to_date: Filter entries on or before this ISO 8601 date.
        event_type: Filter by event type (exact match).
        limit: Maximum number of results to return (default 50).

    Returns:
        A list of dicts, one per matching audit entry, newest first.
    """
    conn.row_factory = sqlite3.Row

    conditions: list[str] = []
    params: list[str | int] = []

    if influencer_name is not None:
        conditions.append("influencer_name = ?")
        params.append(influencer_name)

    if campaign_id is not None:
        conditions.append("campaign_id = ?")
        params.append(campaign_id)

    if from_date is not None:
        conditions.append("timestamp >= ?")
        params.append(from_date)

    if to_date is not None:
        conditions.append("timestamp <= ?")
        params.append(to_date)

    if event_type is not None:
        conditions.append("event_type = ?")
        params.append(event_type)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"SELECT * FROM audit_log {where_clause} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        # Deserialize metadata JSON back to dict if present
        if row_dict.get("metadata") is not None:
            row_dict["metadata"] = json.loads(row_dict["metadata"])
        results.append(row_dict)

    return results


def close_audit_db(conn: sqlite3.Connection) -> None:
    """Close the audit database connection.

    Args:
        conn: The database connection to close.
    """
    conn.close()
