"""Tests for CampaignCPMTracker with engagement-quality-weighted flexibility."""

from decimal import Decimal

from negotiation.campaign.cpm_tracker import CampaignCPMTracker, CPMFlexibility


class TestCPMFlexibility:
    """Tests for the CPMFlexibility dataclass."""

    def test_immutable(self):
        flex = CPMFlexibility(
            target_cpm=Decimal("30"),
            max_allowed_cpm=Decimal("34.50"),
            reason="test reason",
        )
        assert flex.target_cpm == Decimal("30")
        assert flex.max_allowed_cpm == Decimal("34.50")
        assert flex.reason == "test reason"


class TestCampaignCPMTracker:
    """Tests for CampaignCPMTracker flexibility calculations."""

    def _make_tracker(
        self,
        target_min: str = "20",
        target_max: str = "30",
        total: int = 5,
    ) -> CampaignCPMTracker:
        return CampaignCPMTracker(
            campaign_id="camp_001",
            target_min_cpm=Decimal(target_min),
            target_max_cpm=Decimal(target_max),
            total_influencers=total,
        )

    def test_no_agreements_returns_target_max(self):
        """With no agreements, max_allowed should be target_max (no premium)."""
        tracker = self._make_tracker()
        flex = tracker.get_flexibility()
        assert flex.target_cpm == Decimal("30")
        assert flex.max_allowed_cpm == Decimal("30")

    def test_running_average_none_with_no_agreements(self):
        tracker = self._make_tracker()
        assert tracker.running_average_cpm is None

    def test_running_average_calculated(self):
        tracker = self._make_tracker()
        tracker.record_agreement(Decimal("20"))
        tracker.record_agreement(Decimal("30"))
        assert tracker.running_average_cpm == Decimal("25")

    def test_running_average_below_target_gives_more_flexibility(self):
        """When running average is below target, remaining influencers get more room."""
        tracker = self._make_tracker(target_max="30", total=5)
        # Record 2 agreements well below target
        tracker.record_agreement(Decimal("20"))
        tracker.record_agreement(Decimal("20"))

        flex = tracker.get_flexibility()
        # Running avg is $20, target max is $30, savings = $10 per agreement
        # Budget premium = $10 * 2 / 3 = $6.67 (distributed across 3 remaining)
        assert flex.max_allowed_cpm > Decimal("30")

    def test_running_average_above_target_no_extra_budget(self):
        """When running average is at or above target, no budget premium."""
        tracker = self._make_tracker(target_max="30", total=3)
        tracker.record_agreement(Decimal("30"))
        tracker.record_agreement(Decimal("32"))

        flex = tracker.get_flexibility()
        # Running avg is $31, above target -- no budget savings
        # No engagement premium either
        assert flex.max_allowed_cpm == Decimal("30")

    def test_high_engagement_gets_15_percent_premium(self):
        """Influencer with >5% engagement rate gets 15% CPM premium."""
        tracker = self._make_tracker(target_max="30")

        flex = tracker.get_flexibility(influencer_engagement_rate=6.0)
        # 15% of $30 = $4.50
        expected = Decimal("30") + Decimal("30") * Decimal("0.15")
        assert flex.max_allowed_cpm == expected
        assert "high engagement" in flex.reason
        assert "+15%" in flex.reason

    def test_moderate_engagement_gets_8_percent_premium(self):
        """Influencer with >3% engagement rate gets 8% CPM premium."""
        tracker = self._make_tracker(target_max="30")

        flex = tracker.get_flexibility(influencer_engagement_rate=4.0)
        # 8% of $30 = $2.40
        expected = Decimal("30") + Decimal("30") * Decimal("0.08")
        assert flex.max_allowed_cpm == expected
        assert "moderate engagement" in flex.reason
        assert "+8%" in flex.reason

    def test_low_engagement_no_premium(self):
        """Influencer with <=3% engagement gets no premium."""
        tracker = self._make_tracker(target_max="30")

        flex = tracker.get_flexibility(influencer_engagement_rate=2.5)
        assert flex.max_allowed_cpm == Decimal("30")
        assert "low engagement" in flex.reason

    def test_no_engagement_data_no_premium(self):
        """No engagement rate data means no engagement premium."""
        tracker = self._make_tracker(target_max="30")

        flex = tracker.get_flexibility(influencer_engagement_rate=None)
        assert flex.max_allowed_cpm == Decimal("30")
        assert "no engagement data" in flex.reason

    def test_hard_cap_at_120_percent(self):
        """Max allowed CPM never exceeds 120% of target max regardless of premiums."""
        tracker = self._make_tracker(target_max="30", total=5)
        # Record very cheap agreements to create large budget surplus
        tracker.record_agreement(Decimal("10"))
        tracker.record_agreement(Decimal("10"))
        tracker.record_agreement(Decimal("10"))

        # Request flexibility with high engagement (15% premium)
        flex = tracker.get_flexibility(influencer_engagement_rate=8.0)
        hard_cap = Decimal("30") * Decimal("1.20")
        assert flex.max_allowed_cpm <= hard_cap
        assert flex.max_allowed_cpm == hard_cap

    def test_engagement_quality_changes_max_allowed(self):
        """Engagement quality must actually change the max_allowed_cpm."""
        tracker = self._make_tracker(target_max="30")

        flex_none = tracker.get_flexibility(influencer_engagement_rate=None)
        flex_moderate = tracker.get_flexibility(influencer_engagement_rate=4.0)
        flex_high = tracker.get_flexibility(influencer_engagement_rate=6.0)

        assert flex_none.max_allowed_cpm < flex_moderate.max_allowed_cpm
        assert flex_moderate.max_allowed_cpm < flex_high.max_allowed_cpm

    def test_all_influencers_agreed_returns_target_max(self):
        """When all influencers have agreed, no remaining room for budget flex."""
        tracker = self._make_tracker(target_max="30", total=2)
        tracker.record_agreement(Decimal("25"))
        tracker.record_agreement(Decimal("25"))

        flex = tracker.get_flexibility()
        # All agreed, 0 remaining -- no budget premium, no engagement premium
        assert flex.max_allowed_cpm == Decimal("30")

    def test_exactly_3_percent_no_premium(self):
        """Engagement rate of exactly 3.0% does NOT get moderate premium (exclusive >3%)."""
        tracker = self._make_tracker(target_max="30")
        flex = tracker.get_flexibility(influencer_engagement_rate=3.0)
        assert flex.max_allowed_cpm == Decimal("30")

    def test_exactly_5_percent_gets_moderate_not_high(self):
        """Engagement rate of exactly 5.0% gets moderate premium (exclusive >5%)."""
        tracker = self._make_tracker(target_max="30")
        flex = tracker.get_flexibility(influencer_engagement_rate=5.0)
        expected_moderate = Decimal("30") + Decimal("30") * Decimal("0.08")
        assert flex.max_allowed_cpm == expected_moderate
