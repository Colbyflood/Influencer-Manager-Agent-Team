"""Google Sheets client for influencer data operations.

Wraps ``gspread`` to provide typed access to the influencer tracking
spreadsheet with case-insensitive lookup, caching, and error handling.
"""

from __future__ import annotations

import gspread

from negotiation.auth.credentials import get_sheets_client
from negotiation.domain.models import PayRange
from negotiation.sheets.models import InfluencerRow


class SheetsClient:
    """High-level client for reading influencer data from Google Sheets.

    Wraps a ``gspread.Client`` to provide typed access to influencer rows
    with spreadsheet caching and case-insensitive lookup.

    Args:
        gc: An authenticated ``gspread.Client``.
        spreadsheet_key: The Google Sheets spreadsheet ID.
    """

    def __init__(self, gc: gspread.Client, spreadsheet_key: str) -> None:
        self._gc = gc
        self._spreadsheet_key = spreadsheet_key
        self._spreadsheet: gspread.Spreadsheet | None = None

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        """Lazy-load and cache the spreadsheet.

        Returns the cached instance on subsequent calls to avoid redundant
        API calls.

        Returns:
            The opened ``gspread.Spreadsheet``.
        """
        if self._spreadsheet is None:
            self._spreadsheet = self._gc.open_by_key(self._spreadsheet_key)
        return self._spreadsheet

    def get_all_influencers(self, worksheet_name: str = "Sheet1") -> list[InfluencerRow]:
        """Read all influencer rows from the specified worksheet.

        Uses a single ``get_all_records()`` call to fetch data in one API
        request, avoiding per-row rate limiting.

        Args:
            worksheet_name: Name of the worksheet tab. Defaults to
                ``"Sheet1"``.

        Returns:
            A list of ``InfluencerRow`` instances for every valid row.

        Raises:
            ValueError: If the worksheet is empty or has no records.
        """
        spreadsheet = self._get_spreadsheet()
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()

        if not records:
            raise ValueError(f"Worksheet '{worksheet_name}' is empty or has no records")

        rows: list[InfluencerRow] = []
        for record in records:
            # Skip rows with empty name fields (partial data)
            name_value = record.get("Name", "")
            if not str(name_value).strip():
                continue

            rows.append(
                InfluencerRow(
                    name=str(record["Name"]),
                    email=str(record["Email"]),
                    platform=str(record["Platform"]),
                    handle=str(record["Handle"]),
                    average_views=int(record["Average Views"]),
                    min_rate=record["Min Rate"],
                    max_rate=record["Max Rate"],
                    engagement_rate=record.get("Engagement Rate"),
                )
            )

        return rows

    def find_influencer(self, name: str, worksheet_name: str = "Sheet1") -> InfluencerRow:
        """Find a specific influencer by name (case-insensitive).

        Performs a case-insensitive, whitespace-trimmed comparison against
        all rows in the worksheet.

        Args:
            name: The influencer name to search for.
            worksheet_name: Name of the worksheet tab. Defaults to
                ``"Sheet1"``.

        Returns:
            The first matching ``InfluencerRow``.

        Raises:
            ValueError: If no influencer with the given name is found.
        """
        all_influencers = self.get_all_influencers(worksheet_name)
        search_name = name.strip().lower()

        for row in all_influencers:
            if row.name.strip().lower() == search_name:
                return row

        raise ValueError(f"Influencer '{name}' not found in sheet")

    def get_pay_range(self, name: str, worksheet_name: str = "Sheet1") -> PayRange:
        """Look up an influencer's pay range by name.

        Convenience method that combines ``find_influencer`` with
        ``InfluencerRow.to_pay_range()``.  This is the primary method
        the negotiation pipeline will use.

        Args:
            name: The influencer name to search for.
            worksheet_name: Name of the worksheet tab. Defaults to
                ``"Sheet1"``.

        Returns:
            A ``PayRange`` with the influencer's rate data.

        Raises:
            ValueError: If no influencer with the given name is found.
        """
        influencer = self.find_influencer(name, worksheet_name)
        return influencer.to_pay_range()


def create_sheets_client(
    spreadsheet_key: str,
    service_account_path: str | None = None,
) -> SheetsClient:
    """Create a ``SheetsClient`` using service account credentials.

    This is the recommended factory for production use.  It handles
    credential loading via the auth module, then wraps the authenticated
    ``gspread.Client`` in a ``SheetsClient``.

    Args:
        spreadsheet_key: The Google Sheets spreadsheet ID.
        service_account_path: Optional explicit path to the service account
            JSON key file. Falls back to auth module defaults if ``None``.

    Returns:
        A configured ``SheetsClient`` ready for API calls.
    """
    gc = get_sheets_client(service_account_path)
    return SheetsClient(gc, spreadsheet_key)
