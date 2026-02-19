"""Tests for rate boundary enforcement and escalation logic."""

from decimal import Decimal

import pytest

from negotiation.pricing.boundaries import (
    BoundaryResult,
    PricingResult,
    evaluate_proposed_rate,
)


class TestBoundaryResultEnum:
    """Tests for the BoundaryResult enum values."""

    def test_within_range_exists(self):
        assert BoundaryResult.WITHIN_RANGE == "within_range"

    def test_exceeds_ceiling_exists(self):
        assert BoundaryResult.EXCEEDS_CEILING == "exceeds_ceiling"

    def test_below_floor_exists(self):
        assert BoundaryResult.BELOW_FLOOR == "below_floor"

    def test_suspiciously_low_exists(self):
        assert BoundaryResult.SUSPICIOUSLY_LOW == "suspiciously_low"


class TestEvaluateProposedRate:
    """Tests for the core boundary evaluation logic."""

    @pytest.mark.parametrize(
        ("rate", "views", "expected_boundary", "expected_escalate", "has_warning"),
        [
            # Within range: CPM=$25, between floor ($20) and ceiling ($30)
            (Decimal("1250"), 50000, BoundaryResult.WITHIN_RANGE, False, False),
            # Exceeds ceiling: CPM=$35, above ceiling ($30)
            (Decimal("1750"), 50000, BoundaryResult.EXCEEDS_CEILING, True, True),
            # Below floor: CPM=$10, below floor ($20) but above suspiciously_low ($15)
            # Actually CPM=$10 is below $15, so this is suspiciously_low
            # Let's use CPM=$18 instead: rate = 18 * 50 = 900
            (Decimal("900"), 50000, BoundaryResult.BELOW_FLOOR, False, False),
            # Suspiciously low: CPM=$6, well below $15 threshold
            (Decimal("300"), 50000, BoundaryResult.SUSPICIOUSLY_LOW, False, True),
            # Exactly at ceiling: CPM=$30 is within_range (not escalated)
            (Decimal("1500"), 50000, BoundaryResult.WITHIN_RANGE, False, False),
            # Exactly at floor: CPM=$20 is within_range
            (Decimal("1000"), 50000, BoundaryResult.WITHIN_RANGE, False, False),
        ],
        ids=[
            "within_range_25cpm",
            "exceeds_ceiling_35cpm",
            "below_floor_18cpm",
            "suspiciously_low_6cpm",
            "exactly_at_ceiling_30cpm",
            "exactly_at_floor_20cpm",
        ],
    )
    def test_evaluate_boundary_classification(
        self,
        rate: Decimal,
        views: int,
        expected_boundary: BoundaryResult,
        expected_escalate: bool,
        has_warning: bool,
    ):
        result = evaluate_proposed_rate(rate, views)
        assert result.boundary == expected_boundary
        assert result.should_escalate == expected_escalate
        if has_warning:
            assert result.warning is not None
        else:
            assert result.warning is None

    def test_should_escalate_only_when_exceeds_ceiling(self):
        """Only rates above ceiling CPM trigger escalation."""
        # Below ceiling
        result_ok = evaluate_proposed_rate(Decimal("1250"), 50000)
        assert result_ok.should_escalate is False

        # At ceiling
        result_at = evaluate_proposed_rate(Decimal("1500"), 50000)
        assert result_at.should_escalate is False

        # Above ceiling
        result_over = evaluate_proposed_rate(Decimal("1750"), 50000)
        assert result_over.should_escalate is True

    def test_warning_present_for_exceeds_ceiling(self):
        result = evaluate_proposed_rate(Decimal("1750"), 50000)
        assert result.warning is not None
        assert "ceiling" in result.warning.lower() or "exceeds" in result.warning.lower()

    def test_warning_present_for_suspiciously_low(self):
        result = evaluate_proposed_rate(Decimal("300"), 50000)
        assert result.warning is not None
        assert "low" in result.warning.lower() or "suspicious" in result.warning.lower()

    def test_no_warning_for_within_range(self):
        result = evaluate_proposed_rate(Decimal("1250"), 50000)
        assert result.warning is None

    def test_no_warning_for_below_floor(self):
        result = evaluate_proposed_rate(Decimal("900"), 50000)
        assert result.warning is None

    def test_result_contains_rate_and_cpm(self):
        result = evaluate_proposed_rate(Decimal("1250"), 50000)
        assert result.rate == Decimal("1250")
        assert result.cpm == Decimal("25.00")

    def test_configurable_thresholds(self):
        """Custom floor, ceiling, and low_rate_threshold work correctly."""
        # With custom ceiling of $40, CPM=$35 should be within_range
        result = evaluate_proposed_rate(
            Decimal("1750"),
            50000,
            cpm_floor=Decimal("15"),
            cpm_ceiling=Decimal("40"),
            low_rate_threshold=Decimal("10"),
        )
        assert result.boundary == BoundaryResult.WITHIN_RANGE
        assert result.should_escalate is False

    def test_configurable_low_threshold(self):
        """Custom low_rate_threshold detects suspiciously low at different level."""
        # CPM=$18 with threshold $20 should be suspiciously_low
        result = evaluate_proposed_rate(
            Decimal("900"),
            50000,
            cpm_floor=Decimal("20"),
            cpm_ceiling=Decimal("30"),
            low_rate_threshold=Decimal("20"),
        )
        assert result.boundary == BoundaryResult.SUSPICIOUSLY_LOW


class TestPricingResult:
    """Tests for the PricingResult model."""

    def test_pricing_result_is_frozen(self):
        result = evaluate_proposed_rate(Decimal("1250"), 50000)
        with pytest.raises(Exception):
            result.rate = Decimal("9999")  # type: ignore[misc]
