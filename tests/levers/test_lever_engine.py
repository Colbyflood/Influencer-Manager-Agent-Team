"""Tests for the negotiation lever selection engine.

Covers all 8 NEG requirements (NEG-08 through NEG-15) with deterministic
lever priority: floor/ceiling > deliverables > usage rights > product >
syndication > CPM sharing > graceful exit.
"""

from decimal import Decimal

from negotiation.campaign.models import (
    BudgetConstraints,
    Campaign,
    CampaignCPMRange,
    DeliverableScenarios,
    ProductLeverage,
    UsageRights,
    UsageRightsDuration,
    UsageRightsSet,
)
from negotiation.domain.types import Platform
from negotiation.levers.engine import build_opening_context, select_lever
from negotiation.levers.models import LeverAction, NegotiationLeverContext

# ---------------------------------------------------------------------------
# Helpers for building test contexts
# ---------------------------------------------------------------------------


def _budget(
    campaign_budget: str = "10000",
    min_cost: str | None = None,
    max_cost: str | None = None,
    cpm_target: str | None = None,
) -> BudgetConstraints:
    return BudgetConstraints(
        campaign_budget=Decimal(campaign_budget),
        min_cost_per_influencer=Decimal(min_cost) if min_cost else None,
        max_cost_without_approval=Decimal(max_cost) if max_cost else None,
        cpm_target=Decimal(cpm_target) if cpm_target else None,
    )


def _scenarios(
    scenario_1: str = "1x IG Reel + 2x Stories",
    scenario_2: str | None = "1x IG Reel",
    scenario_3: str | None = "1x IG Story",
    content_syndication: bool = False,
) -> DeliverableScenarios:
    return DeliverableScenarios(
        target_deliverables=["1x IG Reel", "2x Stories"],
        scenario_1=scenario_1,
        scenario_2=scenario_2,
        scenario_3=scenario_3,
        content_syndication=content_syndication,
    )


def _usage_rights(
    target_paid: UsageRightsDuration = UsageRightsDuration.days_60,
    min_paid: UsageRightsDuration = UsageRightsDuration.days_30,
) -> UsageRights:
    return UsageRights(
        target=UsageRightsSet(paid_usage=target_paid),
        minimum=UsageRightsSet(paid_usage=min_paid),
    )


def _product(
    available: bool = True,
    description: str = "Premium skincare set",
    value: str = "200",
) -> ProductLeverage:
    return ProductLeverage(
        product_available=available,
        product_description=description,
        product_monetary_value=Decimal(value),
    )


def _ctx(
    their_rate: str = "800",
    our_rate: str = "500",
    views: int = 25000,
    scenario: int = 1,
    usage_tier: str = "target",
    product_offered: bool = False,
    syndication_proposed: bool = False,
    cpm_shared: bool = False,
    round_number: int = 2,
    scenarios: DeliverableScenarios | None = None,
    usage: UsageRights | None = None,
    budget: BudgetConstraints | None = None,
    product: ProductLeverage | None = None,
) -> NegotiationLeverContext:
    return NegotiationLeverContext(
        their_rate=Decimal(their_rate),
        our_current_rate=Decimal(our_rate),
        average_views=views,
        current_scenario=scenario,
        current_usage_tier=usage_tier,
        product_offered=product_offered,
        syndication_proposed=syndication_proposed,
        cpm_shared=cpm_shared,
        round_number=round_number,
        deliverable_scenarios=scenarios,
        usage_rights=usage,
        budget_constraints=budget,
        product_leverage=product,
    )


# ---------------------------------------------------------------------------
# NEG-12: Cost floor enforcement
# ---------------------------------------------------------------------------


class TestEnforceFloor:
    def test_enforce_floor_when_rate_below_minimum(self) -> None:
        """When our_current_rate is below min_cost, enforce floor."""
        ctx = _ctx(
            our_rate="300",
            budget=_budget(min_cost="400"),
            scenarios=_scenarios(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.enforce_floor
        assert result.adjusted_rate == Decimal("400")
        assert result.should_escalate is False
        assert result.should_exit is False


# ---------------------------------------------------------------------------
# NEG-12: Cost ceiling escalation
# ---------------------------------------------------------------------------


class TestEscalateCeiling:
    def test_escalate_ceiling_when_rate_above_max(self) -> None:
        """When their_rate exceeds max_cost_without_approval, escalate."""
        ctx = _ctx(
            their_rate="2000",
            budget=_budget(max_cost="1500"),
            scenarios=_scenarios(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.escalate_ceiling
        assert result.should_escalate is True
        assert result.adjusted_rate is None


# ---------------------------------------------------------------------------
# NEG-09: Trade deliverables
# ---------------------------------------------------------------------------


class TestTradeDeliverables:
    def test_trade_deliverables_scenario_1_to_2(self) -> None:
        """With current_scenario=1 and scenario_2 available, trade down."""
        ctx = _ctx(
            scenario=1,
            scenarios=_scenarios(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.trade_deliverables
        assert result.deliverables_summary is not None
        assert "Reel" in result.deliverables_summary  # scenario_2 text

    def test_trade_deliverables_scenario_2_to_3(self) -> None:
        """With current_scenario=2 and scenario_3 available, trade down."""
        ctx = _ctx(
            scenario=2,
            scenarios=_scenarios(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.trade_deliverables
        assert result.deliverables_summary is not None
        assert "Story" in result.deliverables_summary  # scenario_3 text

    def test_skip_deliverable_trade_at_scenario_3(self) -> None:
        """At scenario 3, should move to next lever (usage rights)."""
        ctx = _ctx(
            scenario=3,
            scenarios=_scenarios(),
            usage=_usage_rights(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action != LeverAction.trade_deliverables


# ---------------------------------------------------------------------------
# NEG-10: Trade usage rights
# ---------------------------------------------------------------------------


class TestTradeUsageRights:
    def test_trade_usage_rights_target_to_minimum(self) -> None:
        """When at target usage and minimum differs, trade down."""
        ctx = _ctx(
            scenario=3,
            usage_tier="target",
            scenarios=_scenarios(),
            usage=_usage_rights(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.trade_usage_rights
        assert result.usage_rights_summary is not None

    def test_skip_usage_rights_when_already_minimum(self) -> None:
        """When already at minimum, skip to next lever."""
        ctx = _ctx(
            scenario=3,
            usage_tier="minimum",
            scenarios=_scenarios(),
            usage=_usage_rights(),
            product=_product(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action != LeverAction.trade_usage_rights


# ---------------------------------------------------------------------------
# NEG-11: Offer product
# ---------------------------------------------------------------------------


class TestOfferProduct:
    def test_offer_product_when_available(self) -> None:
        """When product available and not yet offered, offer it."""
        ctx = _ctx(
            scenario=3,
            usage_tier="minimum",
            product_offered=False,
            scenarios=_scenarios(),
            usage=_usage_rights(),
            product=_product(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.offer_product
        assert "skincare" in result.lever_instructions.lower()

    def test_skip_product_when_already_offered(self) -> None:
        """When product already offered, skip to next lever."""
        ctx = _ctx(
            scenario=3,
            usage_tier="minimum",
            product_offered=True,
            syndication_proposed=False,
            scenarios=_scenarios(content_syndication=True),
            usage=_usage_rights(),
            product=_product(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action != LeverAction.offer_product


# ---------------------------------------------------------------------------
# NEG-14: Propose syndication
# ---------------------------------------------------------------------------


class TestProposeSyndication:
    def test_propose_syndication(self) -> None:
        """When content_syndication=True and not proposed, propose it."""
        ctx = _ctx(
            scenario=3,
            usage_tier="minimum",
            product_offered=True,
            syndication_proposed=False,
            scenarios=_scenarios(content_syndication=True),
            usage=_usage_rights(),
            product=_product(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.propose_syndication


# ---------------------------------------------------------------------------
# NEG-13: Share CPM target
# ---------------------------------------------------------------------------


class TestShareCPMTarget:
    def test_share_cpm_target(self) -> None:
        """When CPM target set and not shared, share it."""
        ctx = _ctx(
            scenario=3,
            usage_tier="minimum",
            product_offered=True,
            syndication_proposed=True,
            cpm_shared=False,
            scenarios=_scenarios(),
            usage=_usage_rights(),
            product=_product(),
            budget=_budget(cpm_target="25"),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.share_cpm_target


# ---------------------------------------------------------------------------
# NEG-15: Graceful exit
# ---------------------------------------------------------------------------


class TestGracefulExit:
    def test_graceful_exit_all_levers_exhausted(self) -> None:
        """When all levers used, exit gracefully."""
        ctx = _ctx(
            scenario=3,
            usage_tier="minimum",
            product_offered=True,
            syndication_proposed=True,
            cpm_shared=True,
            scenarios=_scenarios(),
            usage=_usage_rights(),
            product=_product(),
            budget=_budget(),
        )
        result = select_lever(ctx)
        assert result.action == LeverAction.graceful_exit
        assert result.should_exit is True
        assert result.adjusted_rate is None


# ---------------------------------------------------------------------------
# NEG-08: Build opening context
# ---------------------------------------------------------------------------


class TestBuildOpeningContext:
    def test_build_opening_context_with_scenarios(self) -> None:
        """Opening context uses scenario_1 and CPM floor rate."""
        campaign = Campaign(
            campaign_id="C001",
            client_name="Test Brand",
            budget=Decimal("10000"),
            target_deliverables="1x IG Reel + 2x Stories",
            cpm_range=CampaignCPMRange(min_cpm=Decimal("20"), max_cpm=Decimal("30")),
            platform=Platform.INSTAGRAM,
            timeline="2 weeks",
            created_at="2026-01-01T00:00:00Z",
            deliverables=_scenarios(),
            budget_constraints=_budget(cpm_target="20"),
        )
        rate, deliverables_text = build_opening_context(campaign, average_views=50000)
        # CPM floor = 20, views = 50k -> rate = 50 * 20 = 1000
        assert rate == Decimal("1000.00")
        assert deliverables_text == "1x IG Reel + 2x Stories"

    def test_build_opening_context_without_scenarios(self) -> None:
        """Falls back to target_deliverables when no scenarios exist."""
        campaign = Campaign(
            campaign_id="C002",
            client_name="Test Brand",
            budget=Decimal("5000"),
            target_deliverables="2x TikTok Videos",
            cpm_range=CampaignCPMRange(min_cpm=Decimal("15"), max_cpm=Decimal("25")),
            platform=Platform.TIKTOK,
            timeline="1 week",
            created_at="2026-01-01T00:00:00Z",
        )
        rate, deliverables_text = build_opening_context(campaign, average_views=10000)
        # No budget_constraints.cpm_target, so use cpm_range.min_cpm = 15
        # views = 10k -> rate = 10 * 15 = 150
        assert rate == Decimal("150.00")
        assert deliverables_text == "2x TikTok Videos"


# ---------------------------------------------------------------------------
# Priority tests
# ---------------------------------------------------------------------------


class TestLeverPriority:
    def test_floor_check_takes_priority_over_deliverable_trade(self) -> None:
        """Floor enforcement has higher priority than trading deliverables."""
        ctx = _ctx(
            our_rate="300",
            scenario=1,
            scenarios=_scenarios(),
            budget=_budget(min_cost="400"),
        )
        result = select_lever(ctx)
        # Floor should win over deliverable trade
        assert result.action == LeverAction.enforce_floor
