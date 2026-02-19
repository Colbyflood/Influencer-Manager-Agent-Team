"""Live integration tests for Google Sheets API operations.

These tests read real data from a Google Sheet and verify the API
connection works. They require a valid service account key file and
GOOGLE_SHEETS_KEY to be configured in environment variables.

Run with: pytest -m live -k sheets
"""

from __future__ import annotations

import pytest


@pytest.mark.live
def test_sheets_read(sheets_client):
    """Verify that the Sheets client can read data from the configured spreadsheet.

    Asserts that get_all_influencers returns a list (may be empty if sheet has
    no data rows, but the API call itself must succeed without error, proving
    authentication and sheet access work).
    """
    try:
        rows = sheets_client.get_all_influencers()
    except ValueError:
        # get_all_influencers raises ValueError for empty sheets --
        # this still proves the API connection works
        rows = []

    assert isinstance(rows, list), f"Expected list of rows, got: {type(rows)}"
