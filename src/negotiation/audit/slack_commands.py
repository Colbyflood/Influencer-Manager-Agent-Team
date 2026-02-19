"""Slack /audit command handler with Block Kit formatted responses.

Provides ``register_audit_command`` to register a ``/audit`` slash command
on a Bolt ``App`` instance. The command parses query text like
``"influencer:Jane Doe last:7d"`` and responds with Block Kit formatted
audit results.

Follows the existing command registration pattern from
:mod:`negotiation.slack.commands`.
"""

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING, Any

from negotiation.audit.cli import parse_last_duration
from negotiation.audit.store import query_audit_trail

if TYPE_CHECKING:
    from collections.abc import Callable

_MAX_DISPLAY_ENTRIES = 10


def parse_audit_query(query_text: str) -> dict[str, str]:
    """Parse Slack command text into query parameters.

    Supported syntax::

        influencer:Jane Doe last:7d
        campaign:camp_123
        event_type:escalation last:30d

    Keys: ``influencer``, ``campaign``, ``last``, ``event_type``.
    Values after a key continue until the next key or end of string.

    Args:
        query_text: Raw text from the Slack ``/audit`` command.

    Returns:
        Dict mapping recognized keys to their values.
    """
    params: dict[str, str] = {}
    if not query_text or not query_text.strip():
        return params

    # Match key:value pairs where value runs until next key: or end
    keys = "influencer|campaign|last|event_type"
    pattern = rf"({keys}):(.+?)(?=\s+(?:{keys}):|\s*$)"
    for match in re.finditer(pattern, query_text.strip()):
        key = match.group(1)
        value = match.group(2).strip()
        if value:
            params[key] = value

    return params


def format_audit_blocks(
    results: list[dict[str, Any]],
    query_params: dict[str, str],
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for audit query results.

    Produces a header with query summary, result count, entry sections
    (up to 10), and an overflow note if more results exist.

    Args:
        results: Audit entries from ``query_audit_trail``.
        query_params: The parsed query parameters for the summary header.

    Returns:
        List of Block Kit block dicts.
    """
    total = len(results)
    display = results[:_MAX_DISPLAY_ENTRIES]

    # Build header text
    header_parts: list[str] = ["Audit Trail"]
    if "influencer" in query_params:
        header_parts.append(query_params["influencer"])
    if "campaign" in query_params:
        header_parts.append(query_params["campaign"])
    if "last" in query_params:
        header_parts.append(f"(last {query_params['last']})")

    header_text = ": ".join(header_parts[:2])
    if len(header_parts) > 2:
        header_text += " " + " ".join(header_parts[2:])

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text[:150]},
        },
    ]

    # Count line
    if total == 0:
        count_text = "No entries found."
    elif total <= _MAX_DISPLAY_ENTRIES:
        count_text = f"{total} entries found."
    else:
        count_text = (
            f"{total} entries found (showing most recent {_MAX_DISPLAY_ENTRIES})"
        )

    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": count_text},
        }
    )

    # Entry sections
    for entry in display:
        fields: list[dict[str, str]] = [
            {
                "type": "mrkdwn",
                "text": f"*Timestamp:*\n{entry.get('timestamp', 'N/A')}",
            },
            {
                "type": "mrkdwn",
                "text": f"*Event:*\n{entry.get('event_type', 'N/A')}",
            },
        ]

        if entry.get("campaign_id"):
            fields.append(
                {"type": "mrkdwn", "text": f"*Campaign:*\n{entry['campaign_id']}"}
            )

        if entry.get("negotiation_state"):
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*State:*\n{entry['negotiation_state']}",
                }
            )

        if entry.get("direction"):
            fields.append(
                {"type": "mrkdwn", "text": f"*Direction:*\n{entry['direction']}"}
            )

        if entry.get("rates_used"):
            fields.append(
                {"type": "mrkdwn", "text": f"*Rates:*\n{entry['rates_used']}"}
            )

        blocks.append({"type": "section", "fields": fields})
        blocks.append({"type": "divider"})

    # Overflow note
    if total > _MAX_DISPLAY_ENTRIES:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Showing {_MAX_DISPLAY_ENTRIES} of {total} results. "
                            "Use CLI for full results."
                        ),
                    }
                ],
            }
        )

    return blocks


def register_audit_command(
    app: Any,
    audit_db_conn: sqlite3.Connection,
) -> None:
    """Register the ``/audit`` slash command on a Bolt app.

    Follows the pattern from :func:`negotiation.slack.commands.register_commands`.

    Args:
        app: The Slack Bolt ``App`` instance.
        audit_db_conn: An open SQLite connection to the audit database.
    """

    @app.command("/audit")  # type: ignore[untyped-decorator]
    def handle_audit(
        ack: Callable[[], None],
        command: dict[str, Any],
        respond: Callable[..., None],
    ) -> None:
        """Handle /audit command -- query audit trail via Slack."""
        ack()

        query_text = command.get("text", "").strip()
        query_params = parse_audit_query(query_text)

        # Build query kwargs
        from_date: str | None = None
        if "last" in query_params:
            try:
                from_date = parse_last_duration(query_params["last"])
            except ValueError:
                respond(
                    f"Invalid duration: {query_params['last']}. Use e.g. 7d, 24h, 30d."
                )
                return

        results = query_audit_trail(
            audit_db_conn,
            influencer_name=query_params.get("influencer"),
            campaign_id=query_params.get("campaign"),
            from_date=from_date,
            event_type=query_params.get("event_type"),
        )

        blocks = format_audit_blocks(results, query_params)
        respond(blocks=blocks)
