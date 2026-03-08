"""Tests for campaign Pydantic models: Campaign, CampaignInfluencer, CampaignCPMRange,
and all expanded sub-models for the 42-field ClickUp form."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from negotiation.campaign.models import (
    BudgetConstraints,
    Campaign,
    CampaignBackground,
    CampaignCPMRange,
    CampaignGoals,
    CampaignInfluencer,
    CampaignRequirements,
    DeliverableScenarios,
    DistributionInfo,
    OptimizeFor,
    ProductLeverage,
    UsageRights,
    UsageRightsDuration,
    UsageRightsSet,
)
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
            name="Bob",
            platform=Platform.TIKTOK,
            engagement_rate=5.2,
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


class TestUsageRightsDuration:
    """Tests for the UsageRightsDuration enum."""

    def test_all_values_exist(self):
        expected = [
            "not_required", "days_30", "days_60", "days_90",
            "months_6", "year_1", "perpetual",
        ]
        actual = [d.value for d in UsageRightsDuration]
        assert actual == expected

    def test_ordering_by_index(self):
        durations = list(UsageRightsDuration)
        assert durations.index(UsageRightsDuration.not_required) < durations.index(
            UsageRightsDuration.perpetual
        )
        assert durations.index(UsageRightsDuration.days_30) < durations.index(
            UsageRightsDuration.year_1
        )


class TestOptimizeFor:
    """Tests for the OptimizeFor enum."""

    def test_all_values_exist(self):
        values = [o.value for o in OptimizeFor]
        assert "cpm" in values
        assert "content_volume_usage_rights" in values
        assert "balance" in values
        assert len(values) == 3


class TestCampaignGoals:
    """Tests for the CampaignGoals model."""

    def test_valid_full_construction(self):
        goals = CampaignGoals(
            primary_goal="Brand Awareness",
            secondary_goal="Sales",
            business_context="Q2 product launch",
            optimize_for=OptimizeFor.cpm,
        )
        assert goals.primary_goal == "Brand Awareness"
        assert goals.secondary_goal == "Sales"
        assert goals.optimize_for == OptimizeFor.cpm

    def test_defaults(self):
        goals = CampaignGoals(primary_goal="Brand Awareness")
        assert goals.secondary_goal is None
        assert goals.business_context is None
        assert goals.optimize_for == OptimizeFor.balance

    def test_empty_primary_goal_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            CampaignGoals(primary_goal="  ")

    def test_frozen_immutability(self):
        goals = CampaignGoals(primary_goal="Brand Awareness")
        with pytest.raises(ValidationError):
            goals.primary_goal = "Sales"  # type: ignore[misc]


class TestDeliverableScenarios:
    """Tests for the DeliverableScenarios model."""

    def test_valid_construction(self):
        ds = DeliverableScenarios(
            target_deliverables=["Instagram Reel", "TikTok Video"],
            scenario_1="1 Reel",
            scenario_2="2 Reels + 1 Story",
            scenario_3="3 Reels + 2 Stories",
        )
        assert len(ds.target_deliverables) == 2
        assert ds.scenario_1 == "1 Reel"

    def test_defaults(self):
        ds = DeliverableScenarios(
            target_deliverables=["Reel"],
            scenario_1="1 Reel",
        )
        assert ds.content_syndication is False
        assert ds.scenario_2 is None
        assert ds.scenario_3 is None

    def test_all_none_scenarios_rejected(self):
        with pytest.raises(ValidationError, match="At least one"):
            DeliverableScenarios(target_deliverables=["Reel"])

    def test_frozen_immutability(self):
        ds = DeliverableScenarios(
            target_deliverables=["Reel"],
            scenario_1="1 Reel",
        )
        with pytest.raises(ValidationError):
            ds.scenario_1 = "2 Reels"  # type: ignore[misc]


class TestUsageRightsSet:
    """Tests for the UsageRightsSet model."""

    def test_valid_construction(self):
        urs = UsageRightsSet(
            paid_usage=UsageRightsDuration.days_30,
            whitelisting=UsageRightsDuration.days_60,
            organic_owned=UsageRightsDuration.perpetual,
        )
        assert urs.paid_usage == UsageRightsDuration.days_30
        assert urs.organic_owned == UsageRightsDuration.perpetual

    def test_defaults(self):
        urs = UsageRightsSet()
        assert urs.paid_usage == UsageRightsDuration.not_required
        assert urs.whitelisting == UsageRightsDuration.not_required
        assert urs.organic_owned == UsageRightsDuration.not_required

    def test_frozen_immutability(self):
        urs = UsageRightsSet()
        with pytest.raises(ValidationError):
            urs.paid_usage = UsageRightsDuration.days_30  # type: ignore[misc]


class TestUsageRights:
    """Tests for the UsageRights model."""

    def test_valid_construction(self):
        ur = UsageRights(
            target=UsageRightsSet(
                paid_usage=UsageRightsDuration.days_90,
                whitelisting=UsageRightsDuration.days_60,
            ),
            minimum=UsageRightsSet(
                paid_usage=UsageRightsDuration.days_30,
                whitelisting=UsageRightsDuration.not_required,
            ),
        )
        assert ur.target.paid_usage == UsageRightsDuration.days_90
        assert ur.minimum.paid_usage == UsageRightsDuration.days_30

    def test_minimum_exceeds_target_rejected(self):
        with pytest.raises(ValidationError, match="must not exceed target"):
            UsageRights(
                target=UsageRightsSet(
                    paid_usage=UsageRightsDuration.days_30,
                ),
                minimum=UsageRightsSet(
                    paid_usage=UsageRightsDuration.perpetual,
                ),
            )

    def test_equal_target_and_minimum_accepted(self):
        ur = UsageRights(
            target=UsageRightsSet(paid_usage=UsageRightsDuration.days_60),
            minimum=UsageRightsSet(paid_usage=UsageRightsDuration.days_60),
        )
        assert ur.target.paid_usage == ur.minimum.paid_usage

    def test_frozen_immutability(self):
        ur = UsageRights(
            target=UsageRightsSet(),
            minimum=UsageRightsSet(),
        )
        with pytest.raises(ValidationError):
            ur.target = UsageRightsSet()  # type: ignore[misc]


class TestBudgetConstraints:
    """Tests for the BudgetConstraints model."""

    def test_valid_full_construction(self):
        bc = BudgetConstraints(
            campaign_budget=Decimal("50000"),
            target_influencer_count=10,
            target_cost_range="$2000-$5000",
            min_cost_per_influencer=Decimal("1000"),
            max_cost_without_approval=Decimal("5000"),
            cpm_target=Decimal("25"),
            cpm_leniency_pct=Decimal("15"),
        )
        assert bc.campaign_budget == Decimal("50000")
        assert bc.target_influencer_count == 10
        assert bc.cpm_target == Decimal("25")

    def test_defaults(self):
        bc = BudgetConstraints(campaign_budget=Decimal("10000"))
        assert bc.target_influencer_count is None
        assert bc.target_cost_range is None
        assert bc.min_cost_per_influencer is None
        assert bc.max_cost_without_approval is None
        assert bc.cpm_target is None
        assert bc.cpm_leniency_pct is None

    def test_float_campaign_budget_rejected(self):
        with pytest.raises(ValidationError, match="not float"):
            BudgetConstraints(campaign_budget=50000.0)  # type: ignore[arg-type]

    def test_float_min_cost_rejected(self):
        with pytest.raises(ValidationError, match="not float"):
            BudgetConstraints(
                campaign_budget=Decimal("50000"),
                min_cost_per_influencer=1000.0,  # type: ignore[arg-type]
            )

    def test_float_cpm_target_rejected(self):
        with pytest.raises(ValidationError, match="not float"):
            BudgetConstraints(
                campaign_budget=Decimal("50000"),
                cpm_target=25.0,  # type: ignore[arg-type]
            )

    def test_frozen_immutability(self):
        bc = BudgetConstraints(campaign_budget=Decimal("10000"))
        with pytest.raises(ValidationError):
            bc.campaign_budget = Decimal("20000")  # type: ignore[misc]


class TestProductLeverage:
    """Tests for the ProductLeverage model."""

    def test_valid_construction(self):
        pl = ProductLeverage(
            product_available=True,
            product_description="Premium skincare set",
            product_monetary_value=Decimal("150"),
        )
        assert pl.product_available is True
        assert pl.product_monetary_value == Decimal("150")

    def test_defaults(self):
        pl = ProductLeverage()
        assert pl.product_available is False
        assert pl.product_description is None
        assert pl.product_monetary_value is None

    def test_float_monetary_value_rejected(self):
        with pytest.raises(ValidationError, match="not float"):
            ProductLeverage(product_monetary_value=150.0)  # type: ignore[arg-type]

    def test_frozen_immutability(self):
        pl = ProductLeverage()
        with pytest.raises(ValidationError):
            pl.product_available = True  # type: ignore[misc]


class TestCampaignRequirements:
    """Tests for the CampaignRequirements model."""

    def test_valid_full_construction(self):
        cr = CampaignRequirements(
            exclusivity_required=True,
            exclusivity_term="30 Days",
            exclusivity_description="No competing skincare brands",
            content_posted_organically=True,
            content_approval_required=True,
            revision_rounds=2,
            raw_footage_required="Yes",
            content_delivery_date="2026-04-01 to 2026-04-15",
            content_publish_date="2026-04-20 to 2026-04-30",
        )
        assert cr.exclusivity_required is True
        assert cr.revision_rounds == 2
        assert cr.raw_footage_required == "Yes"

    def test_defaults(self):
        cr = CampaignRequirements()
        assert cr.exclusivity_required is False
        assert cr.exclusivity_term is None
        assert cr.content_posted_organically is False
        assert cr.content_approval_required is False
        assert cr.revision_rounds == 0
        assert cr.raw_footage_required is None
        assert cr.content_delivery_date is None
        assert cr.content_publish_date is None

    def test_frozen_immutability(self):
        cr = CampaignRequirements()
        with pytest.raises(ValidationError):
            cr.exclusivity_required = True  # type: ignore[misc]


class TestCampaignBackground:
    """Tests for the CampaignBackground model."""

    def test_valid_construction(self):
        bg = CampaignBackground(
            client_website="https://acme.com",
            campaign_manager="Jane Doe",
            payment_methods=["PayPal", "ACH"],
            payment_terms="Net 30",
        )
        assert bg.client_website == "https://acme.com"
        assert len(bg.payment_methods) == 2

    def test_defaults(self):
        bg = CampaignBackground()
        assert bg.client_website is None
        assert bg.campaign_manager is None
        assert bg.payment_methods == []
        assert bg.payment_terms is None

    def test_frozen_immutability(self):
        bg = CampaignBackground()
        with pytest.raises(ValidationError):
            bg.client_website = "https://example.com"  # type: ignore[misc]


class TestDistributionInfo:
    """Tests for the DistributionInfo model."""

    def test_valid_construction(self):
        di = DistributionInfo(
            platform_distribution="60% Instagram, 40% TikTok",
            market_distribution="US 80%, UK 20%",
            influencer_size_distribution="Micro 50%, Mid 30%, Macro 20%",
        )
        assert di.platform_distribution == "60% Instagram, 40% TikTok"

    def test_all_fields_optional(self):
        di = DistributionInfo()
        assert di.platform_distribution is None
        assert di.market_distribution is None
        assert di.influencer_size_distribution is None

    def test_frozen_immutability(self):
        di = DistributionInfo()
        with pytest.raises(ValidationError):
            di.platform_distribution = "100% Instagram"  # type: ignore[misc]


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
                min_cpm=Decimal("20"),
                max_cpm=Decimal("30"),
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

    def test_empty_influencer_list_accepted(self, valid_campaign_data):
        """After expansion, empty influencer list is accepted (default=[])."""
        valid_campaign_data["influencers"] = []
        campaign = Campaign(**valid_campaign_data)
        assert campaign.influencers == []

    def test_frozen_immutability(self, valid_campaign_data):
        campaign = Campaign(**valid_campaign_data)
        with pytest.raises(ValidationError):
            campaign.client_name = "New Corp"  # type: ignore[misc]

    def test_decimal_precision_preserved(self, valid_campaign_data):
        valid_campaign_data["budget"] = Decimal("9999.99")
        campaign = Campaign(**valid_campaign_data)
        assert campaign.budget == Decimal("9999.99")


class TestExpandedCampaign:
    """Tests for the expanded Campaign model with all sub-models."""

    @pytest.fixture()
    def base_campaign_data(self):
        return {
            "campaign_id": "task_expanded_001",
            "client_name": "Acme Corp",
            "budget": Decimal("50000"),
            "target_deliverables": "Instagram Reels, TikTok Videos",
            "cpm_range": CampaignCPMRange(
                min_cpm=Decimal("20"),
                max_cpm=Decimal("50"),
            ),
            "platform": Platform.INSTAGRAM,
            "timeline": "2026-04-01 to 2026-04-30",
            "created_at": "2026-03-01T12:00:00Z",
        }

    def test_campaign_with_all_sub_models(self, base_campaign_data):
        """Campaign constructed with all 42-field sub-models."""
        data = {
            **base_campaign_data,
            "background": CampaignBackground(
                client_website="https://acme.com",
                campaign_manager="Jane Doe",
                payment_methods=["PayPal", "ACH"],
                payment_terms="Net 30",
            ),
            "goals": CampaignGoals(
                primary_goal="Brand Awareness",
                secondary_goal="Sales",
                optimize_for=OptimizeFor.cpm,
            ),
            "deliverables": DeliverableScenarios(
                target_deliverables=["Instagram Reel", "TikTok Video"],
                scenario_1="1 Reel",
                scenario_2="2 Reels + 1 Story",
                scenario_3="3 Reels + 2 Stories",
            ),
            "usage_rights": UsageRights(
                target=UsageRightsSet(
                    paid_usage=UsageRightsDuration.days_90,
                    whitelisting=UsageRightsDuration.days_60,
                ),
                minimum=UsageRightsSet(
                    paid_usage=UsageRightsDuration.days_30,
                ),
            ),
            "budget_constraints": BudgetConstraints(
                campaign_budget=Decimal("50000"),
                target_influencer_count=10,
                cpm_target=Decimal("25"),
                cpm_leniency_pct=Decimal("15"),
            ),
            "product_leverage": ProductLeverage(
                product_available=True,
                product_description="Premium skincare set",
                product_monetary_value=Decimal("150"),
            ),
            "requirements": CampaignRequirements(
                exclusivity_required=True,
                exclusivity_term="30 Days",
                content_approval_required=True,
                revision_rounds=2,
            ),
            "distribution": DistributionInfo(
                platform_distribution="60% Instagram, 40% TikTok",
            ),
        }
        campaign = Campaign(**data)
        assert campaign.background is not None
        assert campaign.background.client_website == "https://acme.com"
        assert campaign.goals is not None
        assert campaign.goals.primary_goal == "Brand Awareness"
        assert campaign.deliverables is not None
        assert campaign.deliverables.scenario_1 == "1 Reel"
        assert campaign.usage_rights is not None
        assert campaign.usage_rights.target.paid_usage == UsageRightsDuration.days_90
        assert campaign.budget_constraints is not None
        assert campaign.budget_constraints.cpm_target == Decimal("25")
        assert campaign.product_leverage is not None
        assert campaign.product_leverage.product_available is True
        assert campaign.requirements is not None
        assert campaign.requirements.exclusivity_required is True
        assert campaign.distribution is not None

    def test_backward_compatible_campaign(self, base_campaign_data):
        """Campaign constructed with only original 8 fields (no sub-models)."""
        campaign = Campaign(**base_campaign_data)
        assert campaign.background is None
        assert campaign.goals is None
        assert campaign.deliverables is None
        assert campaign.usage_rights is None
        assert campaign.budget_constraints is None
        assert campaign.product_leverage is None
        assert campaign.requirements is None
        assert campaign.distribution is None

    def test_campaign_with_empty_influencers(self, base_campaign_data):
        """Campaign with influencers=[] no longer raises validation error."""
        base_campaign_data["influencers"] = []
        campaign = Campaign(**base_campaign_data)
        assert campaign.influencers == []

    def test_campaign_default_influencers(self, base_campaign_data):
        """Campaign without influencers key defaults to empty list."""
        # influencers not in base_campaign_data (not passed)
        campaign = Campaign(**base_campaign_data)
        assert campaign.influencers == []
