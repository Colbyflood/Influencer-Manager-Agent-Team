"""SQLite-backed negotiation state store for crash-recovery persistence.

Mirrors the AuditLogger pattern: accepts a sqlite3.Connection, uses
parameterized queries exclusively, and commits synchronously after writes.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from negotiation.state.serializers import serialize_context
from negotiation.state_machine.transitions import TERMINAL_STATES


class NegotiationStateStore:
    """Persist and retrieve negotiation state snapshots in SQLite.

    Each row represents a single negotiation thread's full state at the time
    of the last save.  Terminal negotiations (AGREED / REJECTED) are excluded
    from ``load_active()`` so only in-progress threads are returned.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with an open database connection.

        Args:
            conn: An open sqlite3.Connection whose database already has the
                  ``negotiation_state`` table (see ``init_negotiation_state_table``).
        """
        self._conn = conn

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save(
        self,
        thread_id: str,
        state_machine: Any,
        context: dict[str, Any],
        campaign: Any,
        cpm_tracker_data: dict[str, Any],
        round_count: int,
    ) -> None:
        """Persist a full negotiation snapshot.

        Uses ``INSERT OR REPLACE`` with a ``COALESCE`` subquery so the
        original ``created_at`` is preserved across updates.

        Args:
            thread_id: Unique thread identifier (primary key).
            state_machine: A ``NegotiationStateMachine`` instance.
            context: The negotiation context dict.  Decimal values are
                     automatically serialized to strings via
                     ``serialize_context``.
            campaign: A Pydantic ``Campaign`` model with ``model_dump_json()``.
            cpm_tracker_data: Already-serialized CPM tracker dict (from
                              ``serialize_cpm_tracker`` / ``to_dict``).
            round_count: Current negotiation round number.
        """
        now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Serialize history as list of [from.value, event, to.value] triples
        history_list: list[list[str]] = [
            [from_s.value, event, to_s.value]
            for from_s, event, to_s in state_machine.history
        ]

        self._conn.execute(
            """
            INSERT OR REPLACE INTO negotiation_state (
                thread_id, state, round_count, context_json,
                campaign_json, cpm_tracker_json, history_json,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                COALESCE(
                    (SELECT created_at FROM negotiation_state WHERE thread_id = ?),
                    ?
                ),
                ?
            )
            """,
            (
                thread_id,
                state_machine.state.value,
                round_count,
                serialize_context(context),
                campaign.model_dump_json(),
                json.dumps(cpm_tracker_data),
                json.dumps(history_list),
                thread_id,  # for the COALESCE subquery
                now,        # default created_at on first insert
                now,        # updated_at always set to now
            ),
        )
        self._conn.commit()

    def delete(self, thread_id: str) -> None:
        """Delete a negotiation state row by thread ID.

        Args:
            thread_id: The thread identifier to remove.
        """
        self._conn.execute(
            "DELETE FROM negotiation_state WHERE thread_id = ?",
            (thread_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def load_active(self) -> list[dict[str, Any]]:
        """Load all non-terminal negotiation state rows.

        Terminal states (AGREED, REJECTED) are excluded so only in-progress
        negotiations are returned.

        Returns:
            A list of dicts, one per active negotiation row.
        """
        terminal_values = [s.value for s in TERMINAL_STATES]
        placeholders = ", ".join("?" for _ in terminal_values)

        # Temporarily set row_factory for dict-style access
        prev_factory = self._conn.row_factory
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.execute(
            f"SELECT * FROM negotiation_state WHERE state NOT IN ({placeholders})",
            terminal_values,
        )
        rows = cursor.fetchall()

        # Restore previous row_factory
        self._conn.row_factory = prev_factory

        return [dict(row) for row in rows]
