"""Sheet monitoring for new and modified influencer rows.

Polls campaign sheets via ``SheetsClient``, detects new and modified rows by
comparing against the ``processed_influencers`` SQLite table, and returns
change sets (``SheetDiff``) for downstream processing.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from dataclasses import dataclass, field

from negotiation.campaign.models import Campaign
from negotiation.sheets.client import SheetsClient
from negotiation.sheets.models import InfluencerRow

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
            "SELECT influencer_name, row_hash FROM processed_influencers "
            "WHERE campaign_id = ?",
            (campaign_id,),
        )
        return {name: row_hash for name, row_hash in cursor.fetchall()}

    def _mark_processed(
        self, campaign_id: str, name: str, row_hash: str
    ) -> None:
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

    def mark_rows_processed(
        self, campaign_id: str, rows: list[InfluencerRow]
    ) -> None:
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
