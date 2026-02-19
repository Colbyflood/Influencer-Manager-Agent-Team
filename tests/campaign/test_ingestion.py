"""Tests for the campaign ingestion pipeline.

Covers field mapping loading, custom field parsing, influencer list parsing,
Campaign model building, and the full ingestion orchestration with mocked
external services (ClickUp API, Google Sheets, Slack).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from negotiation.campaign.ingestion import (
    build_campaign,
    ingest_campaign,
    load_field_mapping,
    parse_custom_fields,
    parse_influencer_list,
)
from negotiation.campaign.models import Campaign
from negotiation.domain.types import Platform
from negotiation.sheets.models import InfluencerRow

# --- Fixtures ---


@pytest.fixture()
def sample_field_mapping() -> dict[str, str]:
    """Standard field mapping for tests."""
    return {
        "Client Name": "client_name",
        "Budget": "budget",
        "Target Deliverables": "target_deliverables",
        "Influencer List": "influencers_raw",
        "CPM Min": "cpm_min",
        "CPM Max": "cpm_max",
        "Platform": "platform",
        "Timeline": "timeline",
    }


@pytest.fixture()
def sample_task_data() -> dict[str, Any]:
    """A ClickUp task dict with custom fields matching the field mapping."""
    return {
        "id": "task_123",
        "name": "Test Campaign Task",
        "custom_fields": [
            {"name": "Client Name", "type": "text", "value": "Acme Corp"},
            {"name": "Budget", "type": "number", "value": "5000"},
            {"name": "Target Deliverables", "type": "text", "value": "2 Instagram reels"},
            {
                "name": "Influencer List",
                "type": "text",
                "value": "Alice Johnson, Bob Smith, Charlie Brown",
            },
            {"name": "CPM Min", "type": "number", "value": "10"},
            {"name": "CPM Max", "type": "number", "value": "25"},
            {"name": "Platform", "type": "text", "value": "instagram"},
            {"name": "Timeline", "type": "text", "value": "March 2026"},
        ],
    }


@pytest.fixture()
def mock_influencer_row() -> InfluencerRow:
    """A sample InfluencerRow for Google Sheets mock responses."""
    return InfluencerRow(
        name="Alice Johnson",
        email="alice@example.com",
        platform=Platform.INSTAGRAM,
        handle="@alice",
        average_views=50000,
        min_rate=Decimal("500"),
        max_rate=Decimal("1500"),
    )


def _write_config(tmp_path: Path, content: str) -> Path:
    """Write a YAML config file and return its path."""
    config_file = tmp_path / "campaign_fields.yaml"
    config_file.write_text(content)
    return config_file


# --- load_field_mapping tests ---


class TestLoadFieldMapping:
    """Tests for loading YAML field mapping configuration."""

    def test_loads_valid_config(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            'field_mapping:\n  "Client Name": "client_name"\n  "Budget": "budget"\n',
        )
        result = load_field_mapping(config_path)
        assert result == {"Client Name": "client_name", "Budget": "budget"}

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Campaign fields config not found"):
            load_field_mapping(tmp_path / "nonexistent.yaml")

    def test_empty_field_mapping_returns_empty_dict(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, "other_key: value\n")
        result = load_field_mapping(config_path)
        assert result == {}

    def test_loads_full_config(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                '  "Budget": "budget"\n'
                '  "Influencer List": "influencers_raw"\n'
                "influencer_list_format: comma_separated\n"
            ),
        )
        result = load_field_mapping(config_path)
        assert len(result) == 3
        assert result["Influencer List"] == "influencers_raw"


# --- parse_custom_fields tests ---


class TestParseCustomFields:
    """Tests for extracting values from ClickUp custom fields."""

    def test_extracts_all_mapped_fields(
        self,
        sample_task_data: dict[str, Any],
        sample_field_mapping: dict[str, str],
    ) -> None:
        result = parse_custom_fields(sample_task_data, sample_field_mapping)
        assert result["client_name"] == "Acme Corp"
        assert result["budget"] == 5000.0  # number type cast from string
        assert result["platform"] == "instagram"
        assert result["timeline"] == "March 2026"

    def test_missing_fields_omitted(self, sample_field_mapping: dict[str, str]) -> None:
        """Fields not in task data are simply omitted from result."""
        task_data: dict[str, Any] = {"custom_fields": []}
        result = parse_custom_fields(task_data, sample_field_mapping)
        assert result == {}

    def test_handles_null_values(self, sample_field_mapping: dict[str, str]) -> None:
        """Fields with None values are omitted."""
        task_data: dict[str, Any] = {
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": None},
            ],
        }
        result = parse_custom_fields(task_data, sample_field_mapping)
        assert "client_name" not in result

    def test_handles_number_as_string(self, sample_field_mapping: dict[str, str]) -> None:
        """ClickUp number fields that arrive as strings are cast to float."""
        task_data: dict[str, Any] = {
            "custom_fields": [
                {"name": "Budget", "type": "number", "value": "5000"},
            ],
        }
        result = parse_custom_fields(task_data, sample_field_mapping)
        assert result["budget"] == 5000.0

    def test_handles_date_as_unix_ms(self) -> None:
        """ClickUp date fields are Unix milliseconds, converted to ISO 8601."""
        field_mapping = {"Due Date": "due_date"}
        # 2026-01-15T00:00:00Z in milliseconds
        task_data: dict[str, Any] = {
            "custom_fields": [
                {"name": "Due Date", "type": "date", "value": 1768435200000},
            ],
        }
        result = parse_custom_fields(task_data, field_mapping)
        assert "due_date" in result
        assert "2026" in result["due_date"]

    def test_no_custom_fields_key(self, sample_field_mapping: dict[str, str]) -> None:
        """Task data without custom_fields key returns empty dict."""
        result = parse_custom_fields({}, sample_field_mapping)
        assert result == {}


# --- parse_influencer_list tests ---


class TestParseInfluencerList:
    """Tests for splitting influencer names from text fields."""

    def test_comma_separated(self) -> None:
        result = parse_influencer_list("Alice, Bob, Charlie")
        assert result == ["Alice", "Bob", "Charlie"]

    def test_newline_separated(self) -> None:
        result = parse_influencer_list("Alice\nBob\nCharlie", list_format="newline_separated")
        assert result == ["Alice", "Bob", "Charlie"]

    def test_strips_whitespace(self) -> None:
        result = parse_influencer_list("  Alice  ,  Bob  ,  Charlie  ")
        assert result == ["Alice", "Bob", "Charlie"]

    def test_filters_empty_strings(self) -> None:
        result = parse_influencer_list("Alice,,, Bob,  ,Charlie")
        assert result == ["Alice", "Bob", "Charlie"]

    def test_empty_input(self) -> None:
        result = parse_influencer_list("")
        assert result == []

    def test_single_name(self) -> None:
        result = parse_influencer_list("Alice")
        assert result == ["Alice"]


# --- build_campaign tests ---


class TestBuildCampaign:
    """Tests for constructing Campaign model from parsed fields."""

    def test_builds_valid_campaign(self) -> None:
        parsed = {
            "client_name": "Acme Corp",
            "budget": 5000,
            "target_deliverables": "2 Instagram reels",
            "influencers_raw": "Alice, Bob",
            "cpm_min": 10,
            "cpm_max": 25,
            "platform": "instagram",
            "timeline": "March 2026",
        }
        campaign = build_campaign("task_123", parsed)

        assert isinstance(campaign, Campaign)
        assert campaign.campaign_id == "task_123"
        assert campaign.client_name == "Acme Corp"
        assert campaign.budget == Decimal("5000")
        assert campaign.cpm_range.min_cpm == Decimal("10")
        assert campaign.cpm_range.max_cpm == Decimal("25")
        assert len(campaign.influencers) == 2
        assert campaign.influencers[0].name == "Alice"
        assert campaign.influencers[0].platform == Platform.INSTAGRAM
        assert campaign.platform == Platform.INSTAGRAM
        assert campaign.created_at  # ISO 8601 timestamp present

    def test_defaults_for_missing_fields(self) -> None:
        parsed: dict[str, Any] = {"influencers_raw": "Alice"}
        campaign = build_campaign("task_456", parsed)

        assert campaign.client_name == "Unknown"
        assert campaign.budget == Decimal("0")
        assert campaign.target_deliverables == "TBD"
        assert campaign.timeline == "TBD"
        assert campaign.platform == Platform.INSTAGRAM

    def test_invalid_platform_defaults_to_instagram(self) -> None:
        parsed: dict[str, Any] = {
            "influencers_raw": "Alice",
            "platform": "snapchat",
        }
        campaign = build_campaign("task_789", parsed)
        assert campaign.platform == Platform.INSTAGRAM


# --- ingest_campaign integration tests ---


class TestIngestCampaign:
    """Tests for the full ingestion orchestration with mocked services."""

    @pytest.mark.anyio()
    async def test_all_influencers_found(
        self,
        tmp_path: Path,
        mock_influencer_row: InfluencerRow,
    ) -> None:
        """When all influencers are in the sheet, none are missing."""
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                '  "Budget": "budget"\n'
                '  "Target Deliverables": "target_deliverables"\n'
                '  "Influencer List": "influencers_raw"\n'
                '  "CPM Min": "cpm_min"\n'
                '  "CPM Max": "cpm_max"\n'
                '  "Platform": "platform"\n'
                '  "Timeline": "timeline"\n'
            ),
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_all",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Test Client"},
                {"name": "Budget", "type": "number", "value": "3000"},
                {"name": "Target Deliverables", "type": "text", "value": "1 post"},
                {"name": "Influencer List", "type": "text", "value": "Alice Johnson"},
                {"name": "CPM Min", "type": "number", "value": "10"},
                {"name": "CPM Max", "type": "number", "value": "20"},
                {"name": "Platform", "type": "text", "value": "instagram"},
                {"name": "Timeline", "type": "text", "value": "April 2026"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        sheets_client = MagicMock()
        sheets_client.find_influencer.return_value = mock_influencer_row

        slack_notifier = MagicMock()
        slack_notifier.post_escalation.return_value = "ts_123"

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            result = await ingest_campaign(
                task_id="task_all",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=slack_notifier,
                config_path=config_path,
            )

        assert isinstance(result["campaign"], Campaign)
        assert len(result["found_influencers"]) == 1
        assert len(result["missing_influencers"]) == 0
        # Campaign start notification sent (1 call)
        assert slack_notifier.post_escalation.call_count == 1

    @pytest.mark.anyio()
    async def test_some_influencers_missing(self, tmp_path: Path) -> None:
        """Missing influencers trigger individual Slack alerts."""
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                '  "Budget": "budget"\n'
                '  "Target Deliverables": "target_deliverables"\n'
                '  "Influencer List": "influencers_raw"\n'
                '  "CPM Min": "cpm_min"\n'
                '  "CPM Max": "cpm_max"\n'
                '  "Platform": "platform"\n'
                '  "Timeline": "timeline"\n'
            ),
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_partial",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Brand X"},
                {"name": "Budget", "type": "number", "value": "8000"},
                {"name": "Target Deliverables", "type": "text", "value": "3 videos"},
                {
                    "name": "Influencer List",
                    "type": "text",
                    "value": "Alice Johnson, Unknown Person",
                },
                {"name": "CPM Min", "type": "number", "value": "15"},
                {"name": "CPM Max", "type": "number", "value": "30"},
                {"name": "Platform", "type": "text", "value": "tiktok"},
                {"name": "Timeline", "type": "text", "value": "May 2026"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        alice_row = InfluencerRow(
            name="Alice Johnson",
            email="alice@example.com",
            platform=Platform.TIKTOK,
            handle="@alice",
            average_views=50000,
            min_rate=Decimal("500"),
            max_rate=Decimal("1500"),
        )

        sheets_client = MagicMock()

        def find_influencer_side_effect(name: str) -> InfluencerRow:
            if name == "Alice Johnson":
                return alice_row
            raise ValueError(f"Influencer '{name}' not found in sheet")

        sheets_client.find_influencer.side_effect = find_influencer_side_effect

        slack_notifier = MagicMock()
        slack_notifier.post_escalation.return_value = "ts_456"

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            result = await ingest_campaign(
                task_id="task_partial",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=slack_notifier,
                config_path=config_path,
            )

        assert len(result["found_influencers"]) == 1
        assert result["found_influencers"][0]["name"] == "Alice Johnson"
        assert len(result["missing_influencers"]) == 1
        assert result["missing_influencers"][0] == "Unknown Person"

        # 1 campaign start notification + 1 missing influencer alert = 2
        assert slack_notifier.post_escalation.call_count == 2

    @pytest.mark.anyio()
    async def test_all_influencers_missing(self, tmp_path: Path) -> None:
        """When all influencers are missing, all trigger alerts."""
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                '  "Budget": "budget"\n'
                '  "Target Deliverables": "target_deliverables"\n'
                '  "Influencer List": "influencers_raw"\n'
                '  "CPM Min": "cpm_min"\n'
                '  "CPM Max": "cpm_max"\n'
                '  "Platform": "platform"\n'
                '  "Timeline": "timeline"\n'
            ),
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_none",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Brand Y"},
                {"name": "Budget", "type": "number", "value": "2000"},
                {"name": "Target Deliverables", "type": "text", "value": "1 story"},
                {
                    "name": "Influencer List",
                    "type": "text",
                    "value": "Missing One, Missing Two, Missing Three",
                },
                {"name": "CPM Min", "type": "number", "value": "5"},
                {"name": "CPM Max", "type": "number", "value": "15"},
                {"name": "Platform", "type": "text", "value": "youtube"},
                {"name": "Timeline", "type": "text", "value": "June 2026"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        sheets_client = MagicMock()
        sheets_client.find_influencer.side_effect = ValueError("not found")

        slack_notifier = MagicMock()
        slack_notifier.post_escalation.return_value = "ts_789"

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            result = await ingest_campaign(
                task_id="task_none",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=slack_notifier,
                config_path=config_path,
            )

        assert len(result["found_influencers"]) == 0
        assert len(result["missing_influencers"]) == 3
        assert result["campaign"].platform == Platform.YOUTUBE

        # 1 campaign start notification + 3 missing influencer alerts = 4
        assert slack_notifier.post_escalation.call_count == 4

    @pytest.mark.anyio()
    async def test_ingest_campaign_slack_notifier_none_does_not_crash(
        self,
        tmp_path: Path,
        mock_influencer_row: InfluencerRow,
    ) -> None:
        """When slack_notifier is None, ingest_campaign completes without error."""
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                '  "Budget": "budget"\n'
                '  "Target Deliverables": "target_deliverables"\n'
                '  "Influencer List": "influencers_raw"\n'
                '  "CPM Min": "cpm_min"\n'
                '  "CPM Max": "cpm_max"\n'
                '  "Platform": "platform"\n'
                '  "Timeline": "timeline"\n'
            ),
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_slack_none",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "No Slack Corp"},
                {"name": "Budget", "type": "number", "value": "4000"},
                {"name": "Target Deliverables", "type": "text", "value": "1 reel"},
                {"name": "Influencer List", "type": "text", "value": "Alice Johnson"},
                {"name": "CPM Min", "type": "number", "value": "10"},
                {"name": "CPM Max", "type": "number", "value": "20"},
                {"name": "Platform", "type": "text", "value": "instagram"},
                {"name": "Timeline", "type": "text", "value": "July 2026"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        sheets_client = MagicMock()
        sheets_client.find_influencer.return_value = mock_influencer_row

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            result = await ingest_campaign(
                task_id="task_slack_none",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=None,
                config_path=config_path,
            )

        assert isinstance(result["campaign"], Campaign)
        assert len(result["found_influencers"]) == 1
        assert len(result["missing_influencers"]) == 0

    @pytest.mark.anyio()
    async def test_ingest_campaign_missing_influencers_slack_none(
        self,
        tmp_path: Path,
    ) -> None:
        """Missing influencers with slack_notifier=None does not crash."""
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                '  "Budget": "budget"\n'
                '  "Target Deliverables": "target_deliverables"\n'
                '  "Influencer List": "influencers_raw"\n'
                '  "CPM Min": "cpm_min"\n'
                '  "CPM Max": "cpm_max"\n'
                '  "Platform": "platform"\n'
                '  "Timeline": "timeline"\n'
            ),
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_missing_no_slack",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Brand Z"},
                {"name": "Budget", "type": "number", "value": "6000"},
                {"name": "Target Deliverables", "type": "text", "value": "2 posts"},
                {
                    "name": "Influencer List",
                    "type": "text",
                    "value": "Alice Johnson, Ghost Influencer",
                },
                {"name": "CPM Min", "type": "number", "value": "12"},
                {"name": "CPM Max", "type": "number", "value": "28"},
                {"name": "Platform", "type": "text", "value": "tiktok"},
                {"name": "Timeline", "type": "text", "value": "August 2026"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        alice_row = InfluencerRow(
            name="Alice Johnson",
            email="alice@example.com",
            platform=Platform.TIKTOK,
            handle="@alice",
            average_views=50000,
            min_rate=Decimal("500"),
            max_rate=Decimal("1500"),
        )

        sheets_client = MagicMock()

        def find_influencer_side_effect(name: str) -> InfluencerRow:
            if name == "Alice Johnson":
                return alice_row
            raise ValueError(f"Influencer '{name}' not found in sheet")

        sheets_client.find_influencer.side_effect = find_influencer_side_effect

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            result = await ingest_campaign(
                task_id="task_missing_no_slack",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=None,
                config_path=config_path,
            )

        assert isinstance(result["campaign"], Campaign)
        assert len(result["found_influencers"]) == 1
        assert result["found_influencers"][0]["name"] == "Alice Johnson"
        assert len(result["missing_influencers"]) == 1
        assert result["missing_influencers"][0] == "Ghost Influencer"
