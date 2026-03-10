"""Unit tests for SheetMonitor diff and dedup logic."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from negotiation.campaign.models import Campaign, CampaignCPMRange
from negotiation.sheets.models import InfluencerRow
from negotiation.sheets.monitor import SheetMonitor
from negotiation.state.schema import init_processed_influencers_table


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_campaign(campaign_id: str = "camp-1") -> Campaign:
    """Create a minimal Campaign fixture for testing."""
    return Campaign(
        campaign_id=campaign_id,
        client_name="Test Client",
        budget=Decimal("10000"),
        target_deliverables="1 video",
        influencers=[],
        cpm_range=CampaignCPMRange(min_cpm=Decimal("5"), max_cpm=Decimal("20")),
        platform="youtube",
        timeline="2026-04-01",
        created_at="2026-03-09T00:00:00Z",
        influencer_sheet_tab=None,
        influencer_sheet_id=None,
    )


def _make_row(
    name: str = "Alice",
    email: str = "alice@example.com",
    average_views: int = 50000,
) -> InfluencerRow:
    """Create a minimal InfluencerRow fixture."""
    return InfluencerRow(
        name=name,
        email=email,
        platform="youtube",
        handle=f"@{name.lower()}",
        average_views=average_views,
        min_rate=Decimal("100"),
        max_rate=Decimal("500"),
    )


@pytest.fixture
def monitor() -> tuple[SheetMonitor, MagicMock, sqlite3.Connection]:
    """Return a SheetMonitor with in-memory DB and mocked SheetsClient."""
    conn = sqlite3.connect(":memory:")
    init_processed_influencers_table(conn)
    mock_client = MagicMock()
    mon = SheetMonitor(sheets_client=mock_client, conn=conn)
    return mon, mock_client, conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_new_rows_detected(monitor):
    """New rows not in processed_influencers should appear in diff.new_rows."""
    mon, mock_client, _conn = monitor
    rows = [_make_row("Alice"), _make_row("Bob"), _make_row("Charlie")]
    mock_client.get_all_influencers.return_value = rows

    campaign = _make_campaign()
    diff = mon.check_campaign_sheet(campaign)

    assert len(diff.new_rows) == 3
    assert diff.modified_rows == []
    assert diff.campaign is campaign


def test_processed_rows_excluded(monitor):
    """Already-processed rows with matching hash should be excluded."""
    mon, mock_client, _conn = monitor
    campaign = _make_campaign()

    # Pre-process Alice and Bob
    alice = _make_row("Alice")
    bob = _make_row("Bob")
    mon.mark_rows_processed(campaign.campaign_id, [alice, bob])

    # Sheet returns Alice, Bob (unchanged) + new Charlie
    charlie = _make_row("Charlie")
    mock_client.get_all_influencers.return_value = [alice, bob, charlie]

    diff = mon.check_campaign_sheet(campaign)

    assert len(diff.new_rows) == 1
    assert diff.new_rows[0].name == "Charlie"
    assert diff.modified_rows == []


def test_modified_rows_detected(monitor):
    """Rows with changed data should appear in diff.modified_rows."""
    mon, mock_client, _conn = monitor
    campaign = _make_campaign()

    # Process Alice with original data
    alice_original = _make_row("Alice", average_views=50000)
    mon.mark_rows_processed(campaign.campaign_id, [alice_original])

    # Sheet returns Alice with different average_views
    alice_modified = _make_row("Alice", average_views=75000)
    mock_client.get_all_influencers.return_value = [alice_modified]

    diff = mon.check_campaign_sheet(campaign)

    assert diff.new_rows == []
    assert len(diff.modified_rows) == 1
    modified_row, old_hash = diff.modified_rows[0]
    assert modified_row.name == "Alice"
    assert modified_row.average_views == 75000


def test_mark_rows_processed(monitor):
    """After marking rows processed, re-checking should return empty diff."""
    mon, mock_client, _conn = monitor
    campaign = _make_campaign()

    rows = [_make_row("Alice"), _make_row("Bob")]
    mock_client.get_all_influencers.return_value = rows

    # First check: both new
    diff1 = mon.check_campaign_sheet(campaign)
    assert len(diff1.new_rows) == 2

    # Mark as processed
    mon.mark_rows_processed(campaign.campaign_id, rows)

    # Second check: nothing new
    diff2 = mon.check_campaign_sheet(campaign)
    assert diff2.new_rows == []
    assert diff2.modified_rows == []


def test_empty_sheet_returns_empty_diff(monitor):
    """ValueError from get_all_influencers should produce empty diff."""
    mon, mock_client, _conn = monitor
    campaign = _make_campaign()

    mock_client.get_all_influencers.side_effect = ValueError("empty")

    diff = mon.check_campaign_sheet(campaign)

    assert diff.new_rows == []
    assert diff.modified_rows == []
    assert diff.campaign is campaign
