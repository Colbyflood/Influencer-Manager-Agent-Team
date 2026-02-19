"""Tests for campaign Pydantic models: Campaign, CampaignInfluencer, CampaignCPMRange."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from negotiation.campaign.models import Campaign, CampaignCPMRange, CampaignInfluencer
from negotiation.domain.types import Platform


class TestCampaignInfluencer:
    """Tests for the CampaignInfluencer model."""

    def test_valid_influencer(self):
        inf = CampaignInfluencer(name="Alice", platform=Platform.INSTAGRAM)
        assert inf.name == "Alice"
        assert inf.platform == Platform.INSTAGRAM
        assert inf.engagement_rate is None

    def test_influencer_with_engagement_rate(self):
        inf = CampaignInfluencer(
            name="Bob", platform=Platform.TIKTOK, engagement_rate=5.2,
        )
        assert inf.engagement_rate == 5.2

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            CampaignInfluencer(name="  ", platform=Platform.INSTAGRAM)

    def test_frozen_immutability(self):
        inf = CampaignInfluencer(name="Alice", platform=Platform.INSTAGRAM)
        with pytest.raises(ValidationError):
            inf.name = "Bob"  # type: ignore[misc]


class TestCampaignCPMRange:
    """Tests for the CampaignCPMRange model."""

    def test_valid_range(self):
        cpm = CampaignCPMRange(min_cpm=Decimal("20"), max_cpm=Decimal("30"))
        assert cpm.min_cpm == Decimal("20")
        assert cpm.max_cpm == Decimal("30")

    def test_string_input_accepted(self):
        cpm = CampaignCPMRange(min_cpm="15", max_cpm="25")  # type: ignore[arg-type]
        assert cpm.min_cpm == Decimal("15")
        assert cpm.max_cpm == Decimal("25")

    def test_float_min_cpm_rejected(self):
        with pytest.raises(ValidationError, match="not float"):
            CampaignCPMRange(min_cpm=20.0, max_cpm=Decimal("30"))  # type: ignore[arg-type]

    def test_float_max_cpm_rejected(self):
        with pytest.raises(ValidationError, match="not float"):
            CampaignCPMRange(min_cpm=Decimal("20"), max_cpm=30.0)  # type: ignore[arg-type]

    def test_min_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="must not exceed"):
            CampaignCPMRange(min_cpm=Decimal("50"), max_cpm=Decimal("30"))

    def test_equal_min_max_accepted(self):
        cpm = CampaignCPMRange(min_cpm=Decimal("25"), max_cpm=Decimal("25"))
        assert cpm.min_cpm == cpm.max_cpm

    def test_frozen_immutability(self):
        cpm = CampaignCPMRange(min_cpm=Decimal("20"), max_cpm=Decimal("30"))
        with pytest.raises(ValidationError):
            cpm.min_cpm = Decimal("15")  # type: ignore[misc]


class TestCampaign:
    """Tests for the Campaign model."""

    @pytest.fixture()
    def valid_campaign_data(self):
        return {
            "campaign_id": "task_abc123",
            "client_name": "Acme Corp",
            "budget": Decimal("10000"),
            "target_deliverables": "3 Instagram Reels",
            "influencers": [
                CampaignInfluencer(name="Alice", platform=Platform.INSTAGRAM),
            ],
            "cpm_range": CampaignCPMRange(
                min_cpm=Decimal("20"), max_cpm=Decimal("30"),
            ),
            "platform": Platform.INSTAGRAM,
            "timeline": "2026-03-01 to 2026-03-31",
            "created_at": "2026-02-19T12:00:00Z",
        }

    def test_valid_campaign(self, valid_campaign_data):
        campaign = Campaign(**valid_campaign_data)
        assert campaign.campaign_id == "task_abc123"
        assert campaign.client_name == "Acme Corp"
        assert campaign.budget == Decimal("10000")
        assert len(campaign.influencers) == 1

    def test_float_budget_rejected(self, valid_campaign_data):
        valid_campaign_data["budget"] = 10000.0
        with pytest.raises(ValidationError, match="not float"):
            Campaign(**valid_campaign_data)

    def test_platform_enum_validation(self, valid_campaign_data):
        valid_campaign_data["platform"] = "invalid_platform"
        with pytest.raises(ValidationError):
            Campaign(**valid_campaign_data)

    def test_empty_campaign_id_rejected(self, valid_campaign_data):
        valid_campaign_data["campaign_id"] = "  "
        with pytest.raises(ValidationError, match="must not be empty"):
            Campaign(**valid_campaign_data)

    def test_empty_influencer_list_rejected(self, valid_campaign_data):
        valid_campaign_data["influencers"] = []
        with pytest.raises(ValidationError, match="at least one influencer"):
            Campaign(**valid_campaign_data)

    def test_frozen_immutability(self, valid_campaign_data):
        campaign = Campaign(**valid_campaign_data)
        with pytest.raises(ValidationError):
            campaign.client_name = "New Corp"  # type: ignore[misc]

    def test_decimal_precision_preserved(self, valid_campaign_data):
        valid_campaign_data["budget"] = Decimal("9999.99")
        campaign = Campaign(**valid_campaign_data)
        assert campaign.budget == Decimal("9999.99")
