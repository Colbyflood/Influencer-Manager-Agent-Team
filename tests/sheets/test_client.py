"""Tests for the Google Sheets client (SheetsClient).

All tests use mocked gspread objects -- no real Google Sheets credentials
or API calls are required.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from negotiation.domain.models import PayRange
from negotiation.sheets.client import SheetsClient, create_sheets_client
from negotiation.sheets.models import InfluencerRow

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_sheet_records() -> list[dict[str, object]]:
    """Mimics the output of gspread ``worksheet.get_all_records()``."""
    return [
        {
            "Name": "Creator A",
            "Email": "creatora@email.com",
            "Platform": "instagram",
            "Handle": "@creatora",
            "Average Views": 50000,
            "Min Rate": 1000.0,
            "Max Rate": 1500.0,
        },
        {
            "Name": "Creator B",
            "Email": "creatorb@email.com",
            "Platform": "tiktok",
            "Handle": "@creatorb",
            "Average Views": 100000,
            "Min Rate": 2000.0,
            "Max Rate": 3000.0,
        },
        {
            "Name": "Creator C",
            "Email": "creatorc@email.com",
            "Platform": "youtube",
            "Handle": "@creatorc",
            "Average Views": 200000,
            "Min Rate": 4000.0,
            "Max Rate": 6000.0,
        },
    ]


@pytest.fixture()
def mock_gc(sample_sheet_records: list[dict[str, object]]) -> MagicMock:
    """Return a mocked ``gspread.Client`` wired to sample records."""
    gc = MagicMock()
    worksheet = MagicMock()
    worksheet.get_all_records.return_value = sample_sheet_records

    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = worksheet

    gc.open_by_key.return_value = spreadsheet
    return gc


@pytest.fixture()
def client(mock_gc: MagicMock) -> SheetsClient:
    """Return a ``SheetsClient`` wired to mocked gspread objects."""
    return SheetsClient(gc=mock_gc, spreadsheet_key="test-spreadsheet-key")


# ---------------------------------------------------------------------------
# get_all_influencers
# ---------------------------------------------------------------------------


class TestGetAllInfluencers:
    """Tests for SheetsClient.get_all_influencers."""

    def test_returns_correct_count(self, client: SheetsClient) -> None:
        """Returns one InfluencerRow per record."""
        rows = client.get_all_influencers()
        assert len(rows) == 3

    def test_returns_influencer_row_instances(self, client: SheetsClient) -> None:
        """Every item is an InfluencerRow."""
        rows = client.get_all_influencers()
        for row in rows:
            assert isinstance(row, InfluencerRow)

    def test_maps_dict_keys_to_model_fields(self, client: SheetsClient) -> None:
        """Dict keys are correctly mapped to InfluencerRow fields."""
        rows = client.get_all_influencers()
        first = rows[0]
        assert first.name == "Creator A"
        assert first.email == "creatora@email.com"
        assert first.platform.value == "instagram"
        assert first.handle == "@creatora"
        assert first.average_views == 50000

    def test_float_values_coerced_to_decimal(self, client: SheetsClient) -> None:
        """Float Min Rate and Max Rate are converted to Decimal."""
        rows = client.get_all_influencers()
        first = rows[0]
        assert isinstance(first.min_rate, Decimal)
        assert isinstance(first.max_rate, Decimal)
        assert first.min_rate == Decimal("1000.0")
        assert first.max_rate == Decimal("1500.0")

    def test_skips_rows_with_empty_name(self, mock_gc: MagicMock) -> None:
        """Rows with an empty Name field are skipped."""
        worksheet = MagicMock()
        worksheet.get_all_records.return_value = [
            {
                "Name": "Creator A",
                "Email": "a@email.com",
                "Platform": "instagram",
                "Handle": "@a",
                "Average Views": 50000,
                "Min Rate": 1000.0,
                "Max Rate": 1500.0,
            },
            {
                "Name": "",
                "Email": "",
                "Platform": "",
                "Handle": "",
                "Average Views": 0,
                "Min Rate": 0.0,
                "Max Rate": 0.0,
            },
            {
                "Name": "Creator B",
                "Email": "b@email.com",
                "Platform": "tiktok",
                "Handle": "@b",
                "Average Views": 100000,
                "Min Rate": 2000.0,
                "Max Rate": 3000.0,
            },
        ]
        spreadsheet = MagicMock()
        spreadsheet.worksheet.return_value = worksheet
        mock_gc.open_by_key.return_value = spreadsheet

        client = SheetsClient(gc=mock_gc, spreadsheet_key="key")
        rows = client.get_all_influencers()
        assert len(rows) == 2
        assert rows[0].name == "Creator A"
        assert rows[1].name == "Creator B"

    def test_skips_rows_with_whitespace_only_name(self, mock_gc: MagicMock) -> None:
        """Rows with whitespace-only Name field are skipped."""
        worksheet = MagicMock()
        worksheet.get_all_records.return_value = [
            {
                "Name": "   ",
                "Email": "",
                "Platform": "",
                "Handle": "",
                "Average Views": 0,
                "Min Rate": 0.0,
                "Max Rate": 0.0,
            },
            {
                "Name": "Creator A",
                "Email": "a@email.com",
                "Platform": "instagram",
                "Handle": "@a",
                "Average Views": 50000,
                "Min Rate": 1000.0,
                "Max Rate": 1500.0,
            },
        ]
        spreadsheet = MagicMock()
        spreadsheet.worksheet.return_value = worksheet
        mock_gc.open_by_key.return_value = spreadsheet

        client = SheetsClient(gc=mock_gc, spreadsheet_key="key")
        rows = client.get_all_influencers()
        assert len(rows) == 1
        assert rows[0].name == "Creator A"

    def test_raises_on_empty_worksheet(self, mock_gc: MagicMock) -> None:
        """Raises ValueError when worksheet has no records."""
        worksheet = MagicMock()
        worksheet.get_all_records.return_value = []
        spreadsheet = MagicMock()
        spreadsheet.worksheet.return_value = worksheet
        mock_gc.open_by_key.return_value = spreadsheet

        client = SheetsClient(gc=mock_gc, spreadsheet_key="key")
        with pytest.raises(ValueError, match="empty or has no records"):
            client.get_all_influencers()

    def test_custom_worksheet_name(self, mock_gc: MagicMock) -> None:
        """Passes worksheet_name to spreadsheet.worksheet()."""
        worksheet = MagicMock()
        worksheet.get_all_records.return_value = [
            {
                "Name": "Creator A",
                "Email": "a@email.com",
                "Platform": "instagram",
                "Handle": "@a",
                "Average Views": 50000,
                "Min Rate": 1000.0,
                "Max Rate": 1500.0,
            },
        ]
        spreadsheet = MagicMock()
        spreadsheet.worksheet.return_value = worksheet
        mock_gc.open_by_key.return_value = spreadsheet

        client = SheetsClient(gc=mock_gc, spreadsheet_key="key")
        client.get_all_influencers(worksheet_name="Influencers")
        spreadsheet.worksheet.assert_called_with("Influencers")


# ---------------------------------------------------------------------------
# find_influencer
# ---------------------------------------------------------------------------


class TestFindInfluencer:
    """Tests for SheetsClient.find_influencer."""

    def test_finds_by_exact_name(self, client: SheetsClient) -> None:
        """Finds influencer by exact name match."""
        row = client.find_influencer("Creator A")
        assert row.name == "Creator A"
        assert row.email == "creatora@email.com"

    def test_finds_case_insensitively(self, client: SheetsClient) -> None:
        """Finds influencer regardless of case."""
        row = client.find_influencer("creator a")
        assert row.name == "Creator A"

    def test_finds_upper_case(self, client: SheetsClient) -> None:
        """Finds influencer with uppercase search."""
        row = client.find_influencer("CREATOR B")
        assert row.name == "Creator B"

    def test_finds_mixed_case(self, client: SheetsClient) -> None:
        """Finds influencer with mixed-case search."""
        row = client.find_influencer("cReAtOr C")
        assert row.name == "Creator C"

    def test_finds_with_leading_whitespace(self, client: SheetsClient) -> None:
        """Finds influencer with leading whitespace in search."""
        row = client.find_influencer("  Creator A")
        assert row.name == "Creator A"

    def test_finds_with_trailing_whitespace(self, client: SheetsClient) -> None:
        """Finds influencer with trailing whitespace in search."""
        row = client.find_influencer("Creator B  ")
        assert row.name == "Creator B"

    def test_finds_with_both_whitespace(self, client: SheetsClient) -> None:
        """Finds influencer with leading and trailing whitespace."""
        row = client.find_influencer("  Creator C  ")
        assert row.name == "Creator C"

    def test_raises_when_not_found(self, client: SheetsClient) -> None:
        """Raises ValueError when influencer name is not found."""
        with pytest.raises(ValueError, match="not found in sheet"):
            client.find_influencer("Nonexistent Creator")

    def test_error_message_includes_name(self, client: SheetsClient) -> None:
        """Error message includes the searched name."""
        with pytest.raises(ValueError, match="Unknown Person"):
            client.find_influencer("Unknown Person")


# ---------------------------------------------------------------------------
# get_pay_range
# ---------------------------------------------------------------------------


class TestGetPayRange:
    """Tests for SheetsClient.get_pay_range."""

    def test_returns_pay_range(self, client: SheetsClient) -> None:
        """Returns a PayRange domain model."""
        result = client.get_pay_range("Creator A")
        assert isinstance(result, PayRange)

    def test_correct_values(self, client: SheetsClient) -> None:
        """PayRange has correct min_rate, max_rate, and average_views."""
        result = client.get_pay_range("Creator A")
        assert result.min_rate == Decimal("1000.0")
        assert result.max_rate == Decimal("1500.0")
        assert result.average_views == 50000

    def test_decimal_types(self, client: SheetsClient) -> None:
        """PayRange min_rate and max_rate are Decimal, not float."""
        result = client.get_pay_range("Creator B")
        assert isinstance(result.min_rate, Decimal)
        assert isinstance(result.max_rate, Decimal)

    def test_raises_when_not_found(self, client: SheetsClient) -> None:
        """Raises ValueError when influencer not found."""
        with pytest.raises(ValueError, match="not found in sheet"):
            client.get_pay_range("Nonexistent")


# ---------------------------------------------------------------------------
# create_sheets_client
# ---------------------------------------------------------------------------


class TestCreateSheetsClient:
    """Tests for the create_sheets_client factory function."""

    @patch("negotiation.sheets.client.get_sheets_client")
    def test_creates_sheets_client(self, mock_get: MagicMock) -> None:
        """Creates a SheetsClient with credentials from auth module."""
        mock_gc = MagicMock()
        mock_get.return_value = mock_gc

        result = create_sheets_client("my-spreadsheet-key")

        mock_get.assert_called_once_with(None)
        assert isinstance(result, SheetsClient)
        assert result._gc is mock_gc
        assert result._spreadsheet_key == "my-spreadsheet-key"

    @patch("negotiation.sheets.client.get_sheets_client")
    def test_passes_service_account_path(self, mock_get: MagicMock) -> None:
        """Passes service_account_path to get_sheets_client."""
        mock_gc = MagicMock()
        mock_get.return_value = mock_gc

        create_sheets_client("key", service_account_path="/path/to/sa.json")

        mock_get.assert_called_once_with("/path/to/sa.json")


# ---------------------------------------------------------------------------
# Spreadsheet caching
# ---------------------------------------------------------------------------


class TestSpreadsheetCaching:
    """Tests for lazy-loading and caching of the spreadsheet object."""

    def test_opens_once_on_multiple_calls(self, mock_gc: MagicMock) -> None:
        """open_by_key is called only once despite multiple operations."""
        client = SheetsClient(gc=mock_gc, spreadsheet_key="key")

        # Call _get_spreadsheet multiple times
        ss1 = client._get_spreadsheet()
        ss2 = client._get_spreadsheet()
        ss3 = client._get_spreadsheet()

        mock_gc.open_by_key.assert_called_once_with("key")
        assert ss1 is ss2
        assert ss2 is ss3

    def test_caches_across_different_methods(
        self, client: SheetsClient, mock_gc: MagicMock
    ) -> None:
        """Spreadsheet is cached across get_all_influencers and find_influencer."""
        client.get_all_influencers()
        client.find_influencer("Creator A")
        client.get_pay_range("Creator B")

        # open_by_key should still only be called once
        mock_gc.open_by_key.assert_called_once_with("test-spreadsheet-key")

    def test_initial_spreadsheet_is_none(self) -> None:
        """Spreadsheet is None before first access."""
        gc = MagicMock()
        client = SheetsClient(gc=gc, spreadsheet_key="key")
        assert client._spreadsheet is None

    def test_spreadsheet_set_after_access(self, mock_gc: MagicMock) -> None:
        """Spreadsheet is set after first _get_spreadsheet call."""
        client = SheetsClient(gc=mock_gc, spreadsheet_key="key")
        client._get_spreadsheet()
        assert client._spreadsheet is not None
