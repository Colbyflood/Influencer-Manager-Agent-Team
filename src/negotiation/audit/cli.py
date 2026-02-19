"""CLI query interface for the negotiation audit trail.

Provides an argparse-based command-line tool for querying audit entries
with filters by influencer, campaign, date range, event type, and
a shorthand ``--last`` duration. Output formats: table (default) or JSON.

Per locked decision: CLI for detailed queries by influencer, campaign,
or date range.

Usage::

    python -m negotiation.audit.cli --influencer "Jane Doe" --last 7d
    python -m negotiation.audit.cli --campaign camp_123 --format json
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from negotiation.audit.store import close_audit_db, init_audit_db, query_audit_trail


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for audit trail queries.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(description="Query negotiation audit trail")

    parser.add_argument(
        "--influencer",
        type=str,
        help="Filter by influencer name (case-insensitive matching)",
    )
    parser.add_argument(
        "--campaign",
        type=str,
        help="Filter by campaign ID",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--event-type",
        type=str,
        choices=[
            "email_sent",
            "email_received",
            "state_transition",
            "escalation",
            "agreement",
            "takeover",
            "campaign_start",
            "campaign_influencer_skip",
            "error",
        ],
        help="Filter by event type",
    )
    parser.add_argument(
        "--last",
        type=str,
        help='Shorthand duration (e.g., "7d", "24h", "30d")',
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["table", "json"],
        default="table",
        dest="output_format",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum results (default: 50)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/audit.db",
        help="Path to audit database (default: data/audit.db)",
    )

    return parser


def parse_last_duration(last: str) -> str:
    """Convert a shorthand duration to an ISO 8601 date string.

    Supported formats:
        - ``Nd`` -- N days ago (e.g., ``7d``)
        - ``Nh`` -- N hours ago (e.g., ``24h``)

    Args:
        last: Duration string like ``"7d"`` or ``"24h"``.

    Returns:
        ISO 8601 date-time string for the computed past time.

    Raises:
        ValueError: If the format is not recognized.
    """
    if not last or len(last) < 2:
        msg = f"Unrecognized duration format: {last!r}"
        raise ValueError(msg)

    unit = last[-1]
    try:
        value = int(last[:-1])
    except ValueError:
        msg = f"Unrecognized duration format: {last!r}"
        raise ValueError(msg) from None

    now = datetime.now(tz=UTC)

    if unit == "d":
        result = now - timedelta(days=value)
    elif unit == "h":
        result = now - timedelta(hours=value)
    else:
        msg = f"Unrecognized duration format: {last!r}. Use 'd' for days or 'h' for hours."
        raise ValueError(msg)

    return result.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_table(results: list[dict[str, Any]]) -> str:
    """Format audit results as a human-readable table.

    Columns: Timestamp, Event, Influencer, Campaign, State, Direction.
    Long fields are truncated to fit reasonable terminal width.

    Args:
        results: List of audit entry dicts from ``query_audit_trail``.

    Returns:
        Formatted table string with header row.
    """
    if not results:
        return "No results found."

    headers = ["Timestamp", "Event", "Influencer", "Campaign", "State", "Direction"]
    widths = [20, 25, 20, 15, 20, 10]

    def truncate(value: str | None, width: int) -> str:
        s = str(value or "")
        if len(s) > width:
            return s[: width - 3] + "..."
        return s

    lines: list[str] = []

    # Header
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    lines.append(header_line)
    lines.append("-" * len(header_line))

    # Rows
    for row in results:
        cells = [
            truncate(row.get("timestamp"), widths[0]),
            truncate(row.get("event_type"), widths[1]),
            truncate(row.get("influencer_name"), widths[2]),
            truncate(row.get("campaign_id"), widths[3]),
            truncate(row.get("negotiation_state"), widths[4]),
            truncate(row.get("direction"), widths[5]),
        ]
        lines.append(
            "  ".join(c.ljust(w) for c, w in zip(cells, widths, strict=True))
        )

    return "\n".join(lines)


def format_json(results: list[dict[str, Any]]) -> str:
    """Format audit results as a JSON string.

    Args:
        results: List of audit entry dicts from ``query_audit_trail``.

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(results, indent=2)


def main() -> None:
    """Parse arguments, query audit trail, and print results."""
    parser = build_parser()
    args = parser.parse_args()

    # Resolve --last to --from-date
    from_date = args.from_date
    if args.last:
        from_date = parse_last_duration(args.last)

    # Connect to audit DB
    db_path = Path(args.db)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_audit_db(db_path)

    try:
        results = query_audit_trail(
            conn,
            influencer_name=args.influencer,
            campaign_id=args.campaign,
            from_date=from_date,
            to_date=args.to_date,
            event_type=args.event_type,
            limit=args.limit,
        )

        output = format_json(results) if args.output_format == "json" else format_table(results)

        print(output)
    finally:
        close_audit_db(conn)


if __name__ == "__main__":
    main()
