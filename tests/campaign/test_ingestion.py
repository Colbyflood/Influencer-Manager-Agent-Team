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
    _resolve_dot_paths,
    build_campaign,
    ingest_campaign,
    load_field_mapping,
    parse_boolean,
    parse_custom_fields,
    parse_duration_select,
    parse_influencer_list,
)
from negotiation.campaign.models import Campaign, UsageRightsDuration
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
        mapping, types = load_field_mapping(config_path)
        assert mapping == {"Client Name": "client_name", "Budget": "budget"}
        assert types == {}

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Campaign fields config not found"):
            load_field_mapping(tmp_path / "nonexistent.yaml")

    def test_empty_field_mapping_returns_empty_dict(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, "other_key: value\n")
        mapping, types = load_field_mapping(config_path)
        assert mapping == {}
        assert types == {}

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
        mapping, types = load_field_mapping(config_path)
        assert len(mapping) == 3
        assert mapping["Influencer List"] == "influencers_raw"
        assert types == {}


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

        def find_influencer_side_effect(name: str, **kwargs: Any) -> InfluencerRow:
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

        def find_influencer_side_effect(name: str, **kwargs: Any) -> InfluencerRow:
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


# --- Expanded ingestion tests (42-field) ---


# Full field mapping matching campaign_fields.yaml
_FULL_FIELD_MAPPING: dict[str, str] = {
    "Client Name": "client_name",
    "Client Website": "background.client_website",
    "Campaign Manager": "background.campaign_manager",
    "Payment Methods": "background.payment_methods",
    "Payment Terms": "background.payment_terms",
    "Campaign Type / Primary Goal": "goals.primary_goal",
    "Secondary Goal": "goals.secondary_goal",
    "Business Context": "goals.business_context",
    "Optimize For": "goals.optimize_for",
    "CPM Target": "budget_constraints.cpm_target",
    "CPM Leniency": "budget_constraints.cpm_leniency_pct",
    "Platform Distribution": "distribution.platform_distribution",
    "Market Distribution": "distribution.market_distribution",
    "Influencer Size Distribution": "distribution.influencer_size_distribution",
    "Target Deliverables": "target_deliverables",
    "Content Syndication": "deliverables.content_syndication",
    "Minimum Deliverables Scenario 1": "deliverables.scenario_1",
    "Minimum Deliverables Scenario 2": "deliverables.scenario_2",
    "Minimum Deliverables Scenario 3": "deliverables.scenario_3",
    "Usage Rights - Target for: Paid Usage": "usage_rights.target.paid_usage",
    "Usage Rights - Target for: Whitelisting": "usage_rights.target.whitelisting",
    "Usage Rights - Target for: Organic/Owned": "usage_rights.target.organic_owned",
    "Usage Rights - Minimum for: Paid Usage": "usage_rights.minimum.paid_usage",
    "Usage Rights - Minimum for: Whitelisting": "usage_rights.minimum.whitelisting",
    "Usage Rights - Minimum for: Organic/Owned": "usage_rights.minimum.organic_owned",
    "Campaign Budget": "budget",
    "Target Number of Influencers": "budget_constraints.target_influencer_count",
    "Target Cost per Influencer range": "budget_constraints.target_cost_range",
    "Min Cost per Influencer": "budget_constraints.min_cost_per_influencer",
    "Max Cost without Human Approval": "budget_constraints.max_cost_without_approval",
    "Product as Lever": "product_leverage.product_available",
    "Product Description": "product_leverage.product_description",
    "Product Monetary Value": "product_leverage.product_monetary_value",
    "Category Exclusivity Required": "requirements.exclusivity_required",
    "Exclusivity Term": "requirements.exclusivity_term",
    "Exclusivity Description": "requirements.exclusivity_description",
    "Content Posted Organically": "requirements.content_posted_organically",
    "Content Approval Required": "requirements.content_approval_required",
    "Revision Rounds": "requirements.revision_rounds",
    "Raw Footage Required": "requirements.raw_footage_required",
    "Content Delivery Date": "requirements.content_delivery_date",
    "Content Publish Date": "requirements.content_publish_date",
    "Influencer List": "influencers_raw",
    "Platform": "platform",
    "Timeline": "timeline",
}

_FULL_FIELD_TYPES: dict[str, list[str]] = {
    "number": [
        "CPM Target",
        "CPM Leniency",
        "Campaign Budget",
        "Target Number of Influencers",
        "Min Cost per Influencer",
        "Max Cost without Human Approval",
        "Product Monetary Value",
        "Revision Rounds",
    ],
    "date_range": ["Content Delivery Date", "Content Publish Date"],
    "select": [
        "Campaign Type / Primary Goal",
        "Secondary Goal",
        "Optimize For",
        "Payment Terms",
        "Content Syndication",
        "Exclusivity Term",
        "Raw Footage Required",
        "Content Approval Required",
        "Category Exclusivity Required",
        "Content Posted Organically",
        "Product as Lever",
    ],
    "multi_select": ["Payment Methods", "Target Deliverables"],
    "duration_select": [
        "Usage Rights - Target for: Paid Usage",
        "Usage Rights - Target for: Whitelisting",
        "Usage Rights - Target for: Organic/Owned",
        "Usage Rights - Minimum for: Paid Usage",
        "Usage Rights - Minimum for: Whitelisting",
        "Usage Rights - Minimum for: Organic/Owned",
    ],
}


def _build_full_clickup_task() -> dict[str, Any]:
    """Build a mock ClickUp task with all 42+ custom fields in ClickUp format."""
    return {
        "id": "task_full_42",
        "name": "Full Campaign Task",
        "custom_fields": [
            # Background
            {"name": "Client Name", "type": "text", "value": "Acme Corp"},
            {"name": "Client Website", "type": "url", "value": "https://acme.com"},
            {"name": "Campaign Manager", "type": "text", "value": "Jane Doe"},
            {
                "name": "Payment Methods",
                "type": "labels",
                "value": [{"name": "Wire"}, {"name": "PayPal"}],
            },
            {
                "name": "Payment Terms",
                "type": "drop_down",
                "value": {"name": "Net 30", "id": "pt1"},
            },
            # Goals
            {
                "name": "Campaign Type / Primary Goal",
                "type": "drop_down",
                "value": {"name": "Organic Social Performance", "id": "g1"},
            },
            {
                "name": "Secondary Goal",
                "type": "drop_down",
                "value": {"name": "Brand Awareness", "id": "g2"},
            },
            {"name": "Business Context", "type": "text", "value": "Q1 product launch"},
            {"name": "Optimize For", "type": "drop_down", "value": {"name": "CPM", "id": "o1"}},
            # Budget / CPM
            {"name": "CPM Target", "type": "number", "value": "25"},
            {"name": "CPM Leniency", "type": "number", "value": "10"},
            # Distribution
            {"name": "Platform Distribution", "type": "text", "value": "60% TikTok, 40% IG"},
            {"name": "Market Distribution", "type": "text", "value": "US 80%, UK 20%"},
            {
                "name": "Influencer Size Distribution",
                "type": "text",
                "value": "50% Macro, 50% Micro",
            },
            # Deliverables
            {
                "name": "Target Deliverables",
                "type": "labels",
                "value": [{"name": "TikTok"}, {"name": "Instagram Reel"}],
            },
            {
                "name": "Content Syndication",
                "type": "drop_down",
                "value": {"name": "Yes", "id": "cs1"},
            },
            {"name": "Minimum Deliverables Scenario 1", "type": "text", "value": "1x TikTok"},
            {
                "name": "Minimum Deliverables Scenario 2",
                "type": "text",
                "value": "1x TikTok + 1x IG Reel",
            },
            {
                "name": "Minimum Deliverables Scenario 3",
                "type": "text",
                "value": "2x TikTok + 1x IG Reel",
            },
            # Usage Rights
            {
                "name": "Usage Rights - Target for: Paid Usage",
                "type": "drop_down",
                "value": {"name": "90 Days", "id": "ur1"},
            },
            {
                "name": "Usage Rights - Target for: Whitelisting",
                "type": "drop_down",
                "value": {"name": "60 Days", "id": "ur2"},
            },
            {
                "name": "Usage Rights - Target for: Organic/Owned",
                "type": "drop_down",
                "value": {"name": "Perpetual", "id": "ur3"},
            },
            {
                "name": "Usage Rights - Minimum for: Paid Usage",
                "type": "drop_down",
                "value": {"name": "30 Days", "id": "ur4"},
            },
            {
                "name": "Usage Rights - Minimum for: Whitelisting",
                "type": "drop_down",
                "value": {"name": "30 Days", "id": "ur5"},
            },
            {
                "name": "Usage Rights - Minimum for: Organic/Owned",
                "type": "drop_down",
                "value": {"name": "90 Days", "id": "ur6"},
            },
            # Budget
            {"name": "Campaign Budget", "type": "number", "value": "50000"},
            {"name": "Target Number of Influencers", "type": "number", "value": "10"},
            {"name": "Target Cost per Influencer range", "type": "text", "value": "$3000-$7000"},
            {"name": "Min Cost per Influencer", "type": "number", "value": "2000"},
            {"name": "Max Cost without Human Approval", "type": "number", "value": "5000"},
            # Product Leverage
            {
                "name": "Product as Lever",
                "type": "drop_down",
                "value": {"name": "Yes", "id": "pl1"},
            },
            {"name": "Product Description", "type": "text", "value": "Premium skincare set"},
            {"name": "Product Monetary Value", "type": "number", "value": "150"},
            # Requirements
            {
                "name": "Category Exclusivity Required",
                "type": "drop_down",
                "value": {"name": "Yes", "id": "ex1"},
            },
            {
                "name": "Exclusivity Term",
                "type": "drop_down",
                "value": {"name": "30 Days", "id": "et1"},
            },
            {
                "name": "Exclusivity Description",
                "type": "text",
                "value": "No competing skincare brands",
            },
            {
                "name": "Content Posted Organically",
                "type": "drop_down",
                "value": {"name": "Yes", "id": "cp1"},
            },
            {
                "name": "Content Approval Required",
                "type": "drop_down",
                "value": {"name": "Yes", "id": "ca1"},
            },
            {"name": "Revision Rounds", "type": "number", "value": "2"},
            {
                "name": "Raw Footage Required",
                "type": "drop_down",
                "value": {"name": "Yes", "id": "rf1"},
            },
            {
                "name": "Content Delivery Date",
                "type": "date",
                "value": {"start": 1700000000000, "end": 1702000000000},
            },
            {
                "name": "Content Publish Date",
                "type": "date",
                "value": {"start": 1703000000000, "end": 1705000000000},
            },
            # Influencer / Platform / Timeline
            {"name": "Influencer List", "type": "text", "value": "Alice, Bob, Charlie"},
            {"name": "Platform", "type": "text", "value": "tiktok"},
            {"name": "Timeline", "type": "text", "value": "Q1 2026"},
        ],
    }


class TestParseCustomFieldsExpanded:
    """Tests for expanded parse_custom_fields with all ClickUp field types."""

    def test_parses_all_42_fields(self) -> None:
        """All 42 fields parsed correctly into flat dict with dot-path keys."""
        task_data = _build_full_clickup_task()
        result = parse_custom_fields(task_data, _FULL_FIELD_MAPPING, _FULL_FIELD_TYPES)

        # Text fields
        assert result["client_name"] == "Acme Corp"
        assert result["background.client_website"] == "https://acme.com"
        assert result["background.campaign_manager"] == "Jane Doe"

        # Multi-select
        assert result["background.payment_methods"] == ["Wire", "PayPal"]
        assert result["target_deliverables"] == ["TikTok", "Instagram Reel"]

        # Select fields (string extraction)
        assert result["goals.primary_goal"] == "Organic Social Performance"
        assert result["goals.secondary_goal"] == "Brand Awareness"
        assert result["background.payment_terms"] == "Net 30"

        # Select -> enum string
        assert result["goals.optimize_for"] == "CPM"

        # Number fields
        assert result["budget_constraints.cpm_target"] == 25.0
        assert result["budget_constraints.cpm_leniency_pct"] == 10.0
        assert result["budget"] == 50000.0

        # Boolean select fields (Yes/No)
        assert result["deliverables.content_syndication"] is True
        assert result["product_leverage.product_available"] is True
        assert result["requirements.exclusivity_required"] is True
        assert result["requirements.content_posted_organically"] is True
        assert result["requirements.content_approval_required"] is True

        # Duration select fields
        assert result["usage_rights.target.paid_usage"] == UsageRightsDuration.days_90
        assert result["usage_rights.target.whitelisting"] == UsageRightsDuration.days_60
        assert result["usage_rights.target.organic_owned"] == UsageRightsDuration.perpetual
        assert result["usage_rights.minimum.paid_usage"] == UsageRightsDuration.days_30

        # Date range
        assert "to" in result["requirements.content_delivery_date"]
        assert "to" in result["requirements.content_publish_date"]

    def test_select_field_as_object(self) -> None:
        """ClickUp select field with value as {name, id} object."""
        task_data: dict[str, Any] = {
            "custom_fields": [
                {
                    "name": "Optimize For",
                    "type": "drop_down",
                    "value": {"name": "CPM", "id": "123"},
                },
            ],
        }
        mapping = {"Optimize For": "goals.optimize_for"}
        types = {"select": ["Optimize For"]}
        result = parse_custom_fields(task_data, mapping, types)
        assert result["goals.optimize_for"] == "CPM"

    def test_multi_select_extracts_names(self) -> None:
        """ClickUp multi-select field extracts list of option names."""
        task_data: dict[str, Any] = {
            "custom_fields": [
                {
                    "name": "Payment Methods",
                    "type": "labels",
                    "value": [{"name": "Wire"}, {"name": "ACH"}],
                },
            ],
        }
        mapping = {"Payment Methods": "background.payment_methods"}
        types = {"multi_select": ["Payment Methods"]}
        result = parse_custom_fields(task_data, mapping, types)
        assert result["background.payment_methods"] == ["Wire", "ACH"]


class TestDotPathResolution:
    """Tests for _resolve_dot_paths helper."""

    def test_single_level_keys_stay_flat(self) -> None:
        flat = {"client_name": "Acme", "budget": 5000}
        result = _resolve_dot_paths(flat)
        assert result == {"client_name": "Acme", "budget": 5000}

    def test_two_level_paths(self) -> None:
        flat = {
            "goals.primary_goal": "Performance",
            "goals.secondary_goal": "Awareness",
            "budget_constraints.cpm_target": 25,
        }
        result = _resolve_dot_paths(flat)
        assert result == {
            "goals": {"primary_goal": "Performance", "secondary_goal": "Awareness"},
            "budget_constraints": {"cpm_target": 25},
        }

    def test_three_level_paths(self) -> None:
        flat = {
            "usage_rights.target.paid_usage": UsageRightsDuration.days_90,
            "usage_rights.target.whitelisting": UsageRightsDuration.days_60,
            "usage_rights.minimum.paid_usage": UsageRightsDuration.days_30,
        }
        result = _resolve_dot_paths(flat)
        assert result["usage_rights"]["target"]["paid_usage"] == UsageRightsDuration.days_90
        assert result["usage_rights"]["target"]["whitelisting"] == UsageRightsDuration.days_60
        assert result["usage_rights"]["minimum"]["paid_usage"] == UsageRightsDuration.days_30

    def test_mixed_flat_and_nested(self) -> None:
        flat = {
            "client_name": "Acme",
            "goals.primary_goal": "X",
            "usage_rights.target.paid_usage": UsageRightsDuration.days_30,
        }
        result = _resolve_dot_paths(flat)
        assert result["client_name"] == "Acme"
        assert result["goals"]["primary_goal"] == "X"
        assert result["usage_rights"]["target"]["paid_usage"] == UsageRightsDuration.days_30

    def test_empty_dict(self) -> None:
        assert _resolve_dot_paths({}) == {}


class TestBuildCampaignExpanded:
    """Tests for build_campaign with full 42-field parsed data."""

    def _make_full_parsed_fields(self) -> dict[str, Any]:
        """Return a parsed_fields dict with all 42 fields using dot-path keys."""
        return {
            "client_name": "Acme Corp",
            "background.client_website": "https://acme.com",
            "background.campaign_manager": "Jane Doe",
            "background.payment_methods": ["Wire", "PayPal"],
            "background.payment_terms": "Net 30",
            "goals.primary_goal": "Organic Social Performance",
            "goals.secondary_goal": "Brand Awareness",
            "goals.business_context": "Q1 product launch",
            "goals.optimize_for": "cpm",
            "budget_constraints.cpm_target": 25,
            "budget_constraints.cpm_leniency_pct": 10,
            "distribution.platform_distribution": "60% TikTok, 40% IG",
            "distribution.market_distribution": "US 80%, UK 20%",
            "distribution.influencer_size_distribution": "50% Macro, 50% Micro",
            "target_deliverables": ["TikTok", "Instagram Reel"],
            "deliverables.content_syndication": True,
            "deliverables.scenario_1": "1x TikTok",
            "deliverables.scenario_2": "1x TikTok + 1x IG Reel",
            "deliverables.scenario_3": "2x TikTok + 1x IG Reel",
            "usage_rights.target.paid_usage": UsageRightsDuration.days_90,
            "usage_rights.target.whitelisting": UsageRightsDuration.days_60,
            "usage_rights.target.organic_owned": UsageRightsDuration.perpetual,
            "usage_rights.minimum.paid_usage": UsageRightsDuration.days_30,
            "usage_rights.minimum.whitelisting": UsageRightsDuration.days_30,
            "usage_rights.minimum.organic_owned": UsageRightsDuration.days_90,
            "budget": 50000,
            "budget_constraints.target_influencer_count": 10,
            "budget_constraints.target_cost_range": "$3000-$7000",
            "budget_constraints.min_cost_per_influencer": 2000,
            "budget_constraints.max_cost_without_approval": 5000,
            "product_leverage.product_available": True,
            "product_leverage.product_description": "Premium skincare set",
            "product_leverage.product_monetary_value": 150,
            "requirements.exclusivity_required": True,
            "requirements.exclusivity_term": "30 Days",
            "requirements.exclusivity_description": "No competing skincare brands",
            "requirements.content_posted_organically": True,
            "requirements.content_approval_required": True,
            "requirements.revision_rounds": 2,
            "requirements.raw_footage_required": "Yes",
            "requirements.content_delivery_date": (
                "2023-11-14T22:13:20+00:00 to 2023-12-08T01:46:40+00:00"
            ),
            "requirements.content_publish_date": (
                "2023-12-19T15:33:20+00:00 to 2024-01-11T19:06:40+00:00"
            ),
            "influencers_raw": "Alice, Bob, Charlie",
            "platform": "tiktok",
            "timeline": "Q1 2026",
        }

    def test_all_sub_models_constructed(self) -> None:
        """build_campaign with all 42 fields produces all sub-models."""
        parsed = self._make_full_parsed_fields()
        campaign = build_campaign("task_full", parsed)

        assert isinstance(campaign, Campaign)
        assert campaign.campaign_id == "task_full"
        assert campaign.client_name == "Acme Corp"
        assert campaign.platform == Platform.TIKTOK

        # Sub-models present
        assert campaign.background is not None
        assert campaign.background.client_website == "https://acme.com"
        assert campaign.background.campaign_manager == "Jane Doe"
        assert campaign.background.payment_methods == ["Wire", "PayPal"]

        assert campaign.goals is not None
        assert campaign.goals.primary_goal == "Organic Social Performance"
        assert campaign.goals.secondary_goal == "Brand Awareness"

        assert campaign.deliverables is not None
        assert campaign.deliverables.content_syndication is True
        assert campaign.deliverables.scenario_1 == "1x TikTok"
        assert campaign.deliverables.scenario_2 == "1x TikTok + 1x IG Reel"
        assert campaign.deliverables.scenario_3 == "2x TikTok + 1x IG Reel"
        assert "TikTok" in campaign.deliverables.target_deliverables

        assert campaign.usage_rights is not None
        assert campaign.usage_rights.target.paid_usage == UsageRightsDuration.days_90
        assert campaign.usage_rights.minimum.paid_usage == UsageRightsDuration.days_30

        assert campaign.budget_constraints is not None
        assert campaign.budget_constraints.campaign_budget == Decimal("50000")
        assert campaign.budget_constraints.cpm_target == Decimal("25")
        assert campaign.budget_constraints.target_influencer_count == 10

        assert campaign.product_leverage is not None
        assert campaign.product_leverage.product_available is True
        assert campaign.product_leverage.product_monetary_value == Decimal("150")

        assert campaign.requirements is not None
        assert campaign.requirements.exclusivity_required is True
        assert campaign.requirements.revision_rounds == 2

        assert campaign.distribution is not None
        assert "TikTok" in campaign.distribution.platform_distribution

    def test_backward_compatible_fields_populated(self) -> None:
        """Backward-compatible fields (budget, target_deliverables, cpm_range) populated."""
        parsed = self._make_full_parsed_fields()
        campaign = build_campaign("task_full", parsed)

        assert campaign.budget == Decimal("50000")
        assert "TikTok" in campaign.target_deliverables
        assert campaign.cpm_range.min_cpm == Decimal("0")  # not in parsed
        assert len(campaign.influencers) == 3

    def test_original_8_fields_only_backward_compat(self) -> None:
        """Build with only original 8 fields -- sub-models should be None."""
        parsed: dict[str, Any] = {
            "client_name": "Old Client",
            "budget": 5000,
            "target_deliverables": "2 posts",
            "influencers_raw": "Alice",
            "cpm_min": 10,
            "cpm_max": 25,
            "platform": "instagram",
            "timeline": "March 2026",
        }
        campaign = build_campaign("task_old", parsed)

        assert isinstance(campaign, Campaign)
        assert campaign.client_name == "Old Client"
        assert campaign.budget == Decimal("5000")
        assert campaign.platform == Platform.INSTAGRAM

        # All sub-models should be None
        assert campaign.background is None
        assert campaign.goals is None
        assert campaign.deliverables is None
        assert campaign.usage_rights is None
        assert campaign.budget_constraints is None
        assert campaign.product_leverage is None
        assert campaign.requirements is None
        assert campaign.distribution is None


class TestBooleanParsing:
    """Tests for parse_boolean helper."""

    def test_yes_string(self) -> None:
        assert parse_boolean("Yes") is True

    def test_no_string(self) -> None:
        assert parse_boolean("No") is False

    def test_bool_true(self) -> None:
        assert parse_boolean(True) is True

    def test_bool_false(self) -> None:
        assert parse_boolean(False) is False

    def test_yes_case_insensitive(self) -> None:
        assert parse_boolean("yes") is True
        assert parse_boolean("YES") is True

    def test_no_case_insensitive(self) -> None:
        assert parse_boolean("no") is False

    def test_clickup_select_object_yes(self) -> None:
        assert parse_boolean({"name": "Yes", "id": "123"}) is True

    def test_clickup_select_object_no(self) -> None:
        assert parse_boolean({"name": "No", "id": "456"}) is False


class TestDurationSelectParsing:
    """Tests for parse_duration_select helper."""

    def test_30_days(self) -> None:
        assert parse_duration_select("30 Days") == UsageRightsDuration.days_30

    def test_60_days(self) -> None:
        assert parse_duration_select("60 Days") == UsageRightsDuration.days_60

    def test_90_days(self) -> None:
        assert parse_duration_select("90 Days") == UsageRightsDuration.days_90

    def test_6_months(self) -> None:
        assert parse_duration_select("6 Months") == UsageRightsDuration.months_6

    def test_1_year(self) -> None:
        assert parse_duration_select("1 Year") == UsageRightsDuration.year_1

    def test_perpetual(self) -> None:
        assert parse_duration_select("Perpetual") == UsageRightsDuration.perpetual

    def test_not_required(self) -> None:
        assert parse_duration_select("Not required") == UsageRightsDuration.not_required

    def test_clickup_select_object(self) -> None:
        assert parse_duration_select({"name": "90 Days", "id": "x"}) == UsageRightsDuration.days_90

    def test_unknown_defaults_to_not_required(self) -> None:
        assert parse_duration_select("Unknown Value") == UsageRightsDuration.not_required


class TestLoadFieldMappingWithTypes:
    """Tests for load_field_mapping returning field_types."""

    def test_returns_field_types(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            (
                "field_mapping:\n"
                '  "Client Name": "client_name"\n'
                "field_types:\n"
                '  number: ["CPM Target"]\n'
                '  select: ["Optimize For"]\n'
            ),
        )
        mapping, types = load_field_mapping(config_path)
        assert mapping == {"Client Name": "client_name"}
        assert types == {"number": ["CPM Target"], "select": ["Optimize For"]}

    def test_missing_field_types_returns_empty(self, tmp_path: Path) -> None:
        config_path = _write_config(
            tmp_path,
            'field_mapping:\n  "Client Name": "client_name"\n',
        )
        _mapping, types = load_field_mapping(config_path)
        assert types == {}


# --- Per-campaign sheet routing tests ---


def _minimal_parsed_fields(**overrides: Any) -> dict[str, Any]:
    """Return minimal parsed_fields dict for build_campaign, with optional overrides."""
    base: dict[str, Any] = {
        "client_name": "Test Corp",
        "budget": "5000",
        "cpm_min": "10",
        "cpm_max": "30",
        "platform": "instagram",
        "timeline": "Q1 2026",
        "influencers_raw": "Alice",
    }
    base.update(overrides)
    return base


def _minimal_config_yaml() -> str:
    """Return minimal YAML config string for ingestion tests."""
    return (
        "field_mapping:\n"
        '  "Client Name": "client_name"\n'
        '  "Budget": "budget"\n'
        '  "Target Deliverables": "target_deliverables"\n'
        '  "Influencer List": "influencers_raw"\n'
        '  "CPM Min": "cpm_min"\n'
        '  "CPM Max": "cpm_max"\n'
        '  "Platform": "platform"\n'
        '  "Timeline": "timeline"\n'
        '  "Influencer Sheet Tab": "influencer_sheet_tab"\n'
        '  "Influencer Sheet ID": "influencer_sheet_id"\n'
    )


class TestPerCampaignSheetRouting:
    """Tests for per-campaign sheet tab and spreadsheet ID routing in ingestion."""

    def test_build_campaign_with_sheet_tab(self) -> None:
        """build_campaign populates influencer_sheet_tab from parsed fields."""
        campaign = build_campaign("t1", _minimal_parsed_fields(influencer_sheet_tab="MyTab"))
        assert campaign.influencer_sheet_tab == "MyTab"

    def test_build_campaign_with_sheet_id(self) -> None:
        """build_campaign populates influencer_sheet_id from parsed fields."""
        campaign = build_campaign(
            "t2", _minimal_parsed_fields(influencer_sheet_id="alt-spreadsheet-key")
        )
        assert campaign.influencer_sheet_id == "alt-spreadsheet-key"

    def test_build_campaign_defaults_none(self) -> None:
        """build_campaign defaults both sheet fields to None when not provided."""
        campaign = build_campaign("t3", _minimal_parsed_fields())
        assert campaign.influencer_sheet_tab is None
        assert campaign.influencer_sheet_id is None

    def test_build_campaign_empty_string_becomes_none(self) -> None:
        """Empty/whitespace-only sheet fields are normalized to None."""
        campaign = build_campaign(
            "t4",
            _minimal_parsed_fields(influencer_sheet_tab="", influencer_sheet_id="  "),
        )
        assert campaign.influencer_sheet_tab is None
        assert campaign.influencer_sheet_id is None

    @pytest.mark.anyio()
    async def test_ingest_passes_tab_to_find_influencer(self, tmp_path: Path) -> None:
        """ingest_campaign passes campaign's sheet tab to find_influencer."""
        config_path = _write_config(tmp_path, _minimal_config_yaml())

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_tab",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Tab Corp"},
                {"name": "Budget", "type": "number", "value": "3000"},
                {"name": "Target Deliverables", "type": "text", "value": "1 reel"},
                {"name": "Influencer List", "type": "text", "value": "Alice"},
                {"name": "CPM Min", "type": "number", "value": "10"},
                {"name": "CPM Max", "type": "number", "value": "25"},
                {"name": "Platform", "type": "text", "value": "instagram"},
                {"name": "Timeline", "type": "text", "value": "Q2 2026"},
                {"name": "Influencer Sheet Tab", "type": "text", "value": "CampaignX"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        alice_row = InfluencerRow(
            name="Alice",
            email="alice@example.com",
            platform=Platform.INSTAGRAM,
            handle="@alice",
            average_views=50000,
            min_rate=Decimal("500"),
            max_rate=Decimal("1500"),
        )
        sheets_client = MagicMock()
        sheets_client.find_influencer.return_value = alice_row

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            await ingest_campaign(
                task_id="task_tab",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=None,
                config_path=config_path,
            )

        sheets_client.find_influencer.assert_called_once_with(
            "Alice",
            worksheet_name="CampaignX",
            spreadsheet_key_override=None,
        )

    @pytest.mark.anyio()
    async def test_ingest_passes_sheet_id_to_find_influencer(self, tmp_path: Path) -> None:
        """ingest_campaign passes campaign's sheet ID override to find_influencer."""
        config_path = _write_config(tmp_path, _minimal_config_yaml())

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_sid",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Sheet Corp"},
                {"name": "Budget", "type": "number", "value": "4000"},
                {"name": "Target Deliverables", "type": "text", "value": "2 posts"},
                {"name": "Influencer List", "type": "text", "value": "Alice"},
                {"name": "CPM Min", "type": "number", "value": "15"},
                {"name": "CPM Max", "type": "number", "value": "30"},
                {"name": "Platform", "type": "text", "value": "instagram"},
                {"name": "Timeline", "type": "text", "value": "Q2 2026"},
                {"name": "Influencer Sheet ID", "type": "text", "value": "alt-key-123"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        alice_row = InfluencerRow(
            name="Alice",
            email="alice@example.com",
            platform=Platform.INSTAGRAM,
            handle="@alice",
            average_views=50000,
            min_rate=Decimal("500"),
            max_rate=Decimal("1500"),
        )
        sheets_client = MagicMock()
        sheets_client.find_influencer.return_value = alice_row

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            await ingest_campaign(
                task_id="task_sid",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=None,
                config_path=config_path,
            )

        sheets_client.find_influencer.assert_called_once_with(
            "Alice",
            worksheet_name="Sheet1",
            spreadsheet_key_override="alt-key-123",
        )

    @pytest.mark.anyio()
    async def test_ingest_defaults_to_sheet1_when_no_override(self, tmp_path: Path) -> None:
        """Without sheet tab/id overrides, find_influencer uses Sheet1 and no override."""
        config_path = _write_config(tmp_path, _minimal_config_yaml())

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "task_default",
            "custom_fields": [
                {"name": "Client Name", "type": "text", "value": "Default Corp"},
                {"name": "Budget", "type": "number", "value": "2000"},
                {"name": "Target Deliverables", "type": "text", "value": "1 post"},
                {"name": "Influencer List", "type": "text", "value": "Alice"},
                {"name": "CPM Min", "type": "number", "value": "10"},
                {"name": "CPM Max", "type": "number", "value": "20"},
                {"name": "Platform", "type": "text", "value": "instagram"},
                {"name": "Timeline", "type": "text", "value": "Q3 2026"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        alice_row = InfluencerRow(
            name="Alice",
            email="alice@example.com",
            platform=Platform.INSTAGRAM,
            handle="@alice",
            average_views=50000,
            min_rate=Decimal("500"),
            max_rate=Decimal("1500"),
        )
        sheets_client = MagicMock()
        sheets_client.find_influencer.return_value = alice_row

        with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            await ingest_campaign(
                task_id="task_default",
                api_token="test-token",
                sheets_client=sheets_client,
                slack_notifier=None,
                config_path=config_path,
            )

        sheets_client.find_influencer.assert_called_once_with(
            "Alice",
            worksheet_name="Sheet1",
            spreadsheet_key_override=None,
        )
