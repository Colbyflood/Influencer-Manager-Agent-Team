"""Sheet monitoring for new and modified influencer rows.

Polls campaign sheets via ``SheetsClient``, detects new and modified rows by
comparing against the ``processed_influencers`` SQLite table, and returns
change sets (``SheetDiff``) for downstream processing.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from negotiation.campaign.models import Campaign
from negotiation.sheets.client import SheetsClient
from negotiation.sheets.models import InfluencerRow
from negotiation.state.schema import init_processed_influencers_table

logger = logging.getLogger(__name__)


@dataclass
class SheetDiff:
    """Result of comparing current sheet data against processed records.

    Attributes:
        campaign: The campaign whose sheet was checked.
        new_rows: Influencer rows not previously processed.
        modified_rows: Rows whose data changed since last processing.
            Each entry is a tuple of (current_row, old_hash).
    """

    campaign: Campaign
    new_rows: list[InfluencerRow] = field(default_factory=list)
    modified_rows: list[tuple[InfluencerRow, str]] = field(default_factory=list)


class SheetMonitor:
    """Monitors campaign sheets for new and modified influencer rows.

    Compares live sheet data against the ``processed_influencers`` SQLite table
    to detect additions and modifications.  Already-processed rows with
    unchanged data are excluded from results.

    Args:
        sheets_client: An authenticated ``SheetsClient`` for reading sheets.
        conn: An open ``sqlite3.Connection`` with the
            ``processed_influencers`` table already created.
    """

    def __init__(self, sheets_client: SheetsClient, conn: sqlite3.Connection) -> None:
        self._sheets_client = sheets_client
        self._conn = conn

    @staticmethod
    def _compute_row_hash(row: InfluencerRow) -> str:
        """Compute a SHA-256 hex digest of the serialized row data.

        Args:
            row: The influencer row to hash.

        Returns:
            A hex string representing the SHA-256 hash.
        """
        return hashlib.sha256(row.model_dump_json().encode()).hexdigest()

    def _get_processed(self, campaign_id: str) -> dict[str, str]:
        """Return previously processed influencer names and their row hashes.

        Args:
            campaign_id: The campaign identifier to look up.

        Returns:
            A dict mapping influencer_name to row_hash for all processed
            rows in the given campaign.
        """
        cursor = self._conn.execute(
            "SELECT influencer_name, row_hash FROM processed_influencers WHERE campaign_id = ?",
            (campaign_id,),
        )
        return {name: row_hash for name, row_hash in cursor.fetchall()}

    def _mark_processed(self, campaign_id: str, name: str, row_hash: str) -> None:
        """Insert or update a processed influencer record.

        Uses INSERT OR REPLACE to upsert -- if the (campaign_id, influencer_name)
        pair already exists, the row_hash and processed_at are updated.

        Args:
            campaign_id: The campaign identifier.
            name: The influencer name.
            row_hash: The SHA-256 hash of the current row data.
        """
        self._conn.execute(
            "INSERT OR REPLACE INTO processed_influencers "
            "(campaign_id, influencer_name, row_hash) VALUES (?, ?, ?)",
            (campaign_id, name, row_hash),
        )
        self._conn.commit()

    def check_campaign_sheet(self, campaign: Campaign) -> SheetDiff:
        """Check a campaign's sheet for new and modified influencer rows.

        Fetches all influencer rows from the campaign's sheet, compares each
        against previously processed records, and returns a ``SheetDiff``
        containing new and modified rows.

        Args:
            campaign: The campaign whose sheet to check.

        Returns:
            A ``SheetDiff`` with new and modified rows.  Returns an empty
            diff if the sheet is empty or an error occurs.
        """
        try:
            rows = self._sheets_client.get_all_influencers(
                worksheet_name=campaign.influencer_sheet_tab or "Sheet1",
                spreadsheet_key_override=campaign.influencer_sheet_id,
            )
        except (ValueError, Exception) as exc:
            logger.warning(
                "Failed to read sheet for campaign %s: %s",
                campaign.campaign_id,
                exc,
            )
            return SheetDiff(campaign=campaign)

        processed = self._get_processed(campaign.campaign_id)
        diff = SheetDiff(campaign=campaign)

        for row in rows:
            row_hash = self._compute_row_hash(row)

            if row.name not in processed:
                diff.new_rows.append(row)
            elif processed[row.name] != row_hash:
                diff.modified_rows.append((row, processed[row.name]))
            # else: already processed with same hash -- skip

        return diff

    def mark_rows_processed(self, campaign_id: str, rows: list[InfluencerRow]) -> None:
        """Mark a batch of influencer rows as processed.

        Should be called after successful negotiation start to prevent
        duplicate outreach on subsequent polls.

        Args:
            campaign_id: The campaign identifier.
            rows: The influencer rows to mark as processed.
        """
        for row in rows:
            row_hash = self._compute_row_hash(row)
            self._mark_processed(campaign_id, row.name, row_hash)


async def run_sheet_monitor_loop(services: dict[str, Any]) -> None:
    """Poll campaign sheets hourly for new and modified influencer rows.

    Discovers new influencer rows and auto-starts negotiations via
    ``start_negotiations_for_campaign``.  Sends Slack escalation alerts
    for rows modified after negotiation began.  Pre-seeds already-negotiated
    influencers as processed on first encounter to prevent duplicate outreach.

    Follows the same pattern as ``renew_gmail_watch_periodically`` in app.py.

    Args:
        services: The services dict from ``initialize_services()``.
    """
    sheets_client = services["sheets_client"]
    negotiation_states: dict[str, dict[str, Any]] = services.get("negotiation_states", {})
    slack_notifier = services.get("slack_notifier")
    state_conn = services["audit_conn"]

    monitor = SheetMonitor(sheets_client, state_conn)
    init_processed_influencers_table(state_conn)
    logger.info("Sheet monitor started")

    while True:
        try:
            # Collect unique campaigns from active negotiations that have sheet routing
            seen_campaign_ids: set[str] = set()
            campaigns: list[Campaign] = []
            for entry in negotiation_states.values():
                campaign: Campaign = entry["campaign"]
                if campaign.campaign_id in seen_campaign_ids:
                    continue
                if not (campaign.influencer_sheet_tab or campaign.influencer_sheet_id):
                    continue
                seen_campaign_ids.add(campaign.campaign_id)
                campaigns.append(campaign)

            for campaign in campaigns:
                try:
                    # Pre-seed existing negotiations as processed to prevent duplicates
                    processed = monitor._get_processed(campaign.campaign_id)
                    for entry in negotiation_states.values():
                        entry_campaign: Campaign = entry["campaign"]
                        if entry_campaign.campaign_id != campaign.campaign_id:
                            continue
                        inf_name = entry.get("context", {}).get("influencer_name")
                        if inf_name and inf_name not in processed:
                            monitor._mark_processed(campaign.campaign_id, inf_name, "pre-seeded")

                    diff = monitor.check_campaign_sheet(campaign)

                    # Handle new rows (MON-02): auto-start negotiations
                    if diff.new_rows:
                        found_influencers = [
                            {"name": row.name, "sheet_data": row} for row in diff.new_rows
                        ]
                        # Late import to avoid circular imports
                        from negotiation.app import start_negotiations_for_campaign

                        await start_negotiations_for_campaign(
                            found_influencers=found_influencers,
                            campaign=campaign,
                            services=services,
                        )
                        monitor.mark_rows_processed(campaign.campaign_id, diff.new_rows)
                        logger.info(
                            "Sheet monitor: %d new influencers found for campaign %s",
                            len(diff.new_rows),
                            campaign.campaign_id,
                        )

                    # Handle modified rows (MON-03): Slack alerts
                    if diff.modified_rows:
                        for row, _old_hash in diff.modified_rows:
                            if slack_notifier is not None:
                                blocks = [
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": (
                                                "*Influencer row modified"
                                                " after negotiation started*\n"
                                                f"*Campaign:* {campaign.client_name}\n"
                                                f"*Influencer:* {row.name}\n"
                                                f"Please review the updated row data."
                                            ),
                                        },
                                    }
                                ]
                                fallback_text = (
                                    f"Influencer row modified: {row.name} "
                                    f"in campaign {campaign.client_name}"
                                )
                                slack_notifier.post_escalation(
                                    blocks=blocks, fallback_text=fallback_text
                                )
                            # Update stored hash
                            monitor._mark_processed(
                                campaign.campaign_id,
                                row.name,
                                monitor._compute_row_hash(row),
                            )
                        logger.info(
                            "Sheet monitor: %d modified rows in campaign %s",
                            len(diff.modified_rows),
                            campaign.campaign_id,
                        )

                except Exception:
                    logger.warning(
                        "Sheet monitor error for campaign %s",
                        campaign.campaign_id,
                        exc_info=True,
                    )

        except Exception:
            logger.warning("Sheet monitor loop iteration error", exc_info=True)

        await asyncio.sleep(3600)
