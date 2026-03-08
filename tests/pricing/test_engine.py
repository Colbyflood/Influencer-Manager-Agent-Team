"""Tests for CPM-based rate calculation engine."""

from decimal import Decimal

import pytest

from negotiation.domain.errors import PricingError
from negotiation.pricing.engine import (
    CPM_CEILING,
    CPM_FLOOR,
    calculate_cpm_from_rate,
    calculate_initial_offer,
    calculate_rate,
    derive_cpm_bounds,
)


class TestCalculateRate:
    """Tests for the core CPM rate calculation."""

    @pytest.mark.parametrize(
        ("average_views", "cpm", "expected"),
        [
            (100, Decimal("20"), Decimal("2.00")),
            (1000, Decimal("20"), Decimal("20.00")),
            (50000, Decimal("20"), Decimal("1000.00")),
            (500000, Decimal("20"), Decimal("10000.00")),
            (10000000, Decimal("20"), Decimal("200000.00")),
            (50000, Decimal("25"), Decimal("1250.00")),
            (50000, Decimal("30"), Decimal("1500.00")),
            (1, Decimal("20"), Decimal("0.02")),
            (999, Decimal("20"), Decimal("19.98")),
        ],
        ids=[
            "100_views",
            "1k_views",
            "50k_views",
            "500k_views",
            "10m_views",
            "50k_views_25cpm",
            "50k_views_30cpm",
            "1_view",
            "999_views",
        ],
    )
    def test_calculate_rate_returns_correct_decimal(
        self, average_views: int, cpm: Decimal, expected: Decimal
    ):
        result = calculate_rate(average_views, cpm)
        assert result == expected
        assert isinstance(result, Decimal)

    def test_calculate_rate_zero_views_raises_pricing_error(self):
        with pytest.raises(PricingError, match="average_views must be positive"):
            calculate_rate(0, Decimal("20"))

    def test_calculate_rate_negative_views_raises_pricing_error(self):
        with pytest.raises(PricingError, match="average_views must be positive"):
            calculate_rate(-100, Decimal("20"))

    def test_calculate_rate_returns_exact_decimal_not_float(self):
        """Verify Decimal precision -- no floating point approximation."""
        result = calculate_rate(50000, Decimal("20"))
        # Must be exactly equal, not approximately equal
        assert result == Decimal("1000.00")
        # Ensure two decimal places
        assert result.as_tuple().exponent == -2


class TestCalculateInitialOffer:
    """Tests for initial offer calculation using CPM floor."""

    def test_initial_offer_uses_cpm_floor(self):
        result = calculate_initial_offer(50000)
        assert result == Decimal("1000.00")

    def test_initial_offer_with_custom_cpm_floor(self):
        result = calculate_initial_offer(50000, cpm_floor=Decimal("25"))
        assert result == Decimal("1250.00")

    def test_initial_offer_small_views(self):
        result = calculate_initial_offer(100)
        assert result == Decimal("2.00")

    def test_initial_offer_large_views(self):
        result = calculate_initial_offer(10000000)
        assert result == Decimal("200000.00")

    def test_initial_offer_zero_views_raises_pricing_error(self):
        with pytest.raises(PricingError):
            calculate_initial_offer(0)


class TestCalculateCpmFromRate:
    """Tests for back-calculating CPM from a proposed rate."""

    @pytest.mark.parametrize(
        ("rate", "average_views", "expected_cpm"),
        [
            (Decimal("1000"), 50000, Decimal("20.00")),
            (Decimal("1500"), 50000, Decimal("30.00")),
            (Decimal("1250"), 50000, Decimal("25.00")),
            (Decimal("1750"), 50000, Decimal("35.00")),
            (Decimal("500"), 50000, Decimal("10.00")),
            (Decimal("2"), 100, Decimal("20.00")),
        ],
        ids=[
            "1000_rate_50k",
            "1500_rate_50k",
            "1250_rate_50k",
            "1750_rate_50k",
            "500_rate_50k",
            "2_rate_100",
        ],
    )
    def test_calculate_cpm_back_calculates_correctly(
        self, rate: Decimal, average_views: int, expected_cpm: Decimal
    ):
        result = calculate_cpm_from_rate(rate, average_views)
        assert result == expected_cpm
        assert isinstance(result, Decimal)

    def test_calculate_cpm_zero_views_raises_pricing_error(self):
        with pytest.raises(PricingError, match="average_views must be positive"):
            calculate_cpm_from_rate(Decimal("1000"), 0)

    def test_calculate_cpm_negative_views_raises_pricing_error(self):
        with pytest.raises(PricingError, match="average_views must be positive"):
            calculate_cpm_from_rate(Decimal("1000"), -50)

    def test_calculate_cpm_returns_exact_decimal(self):
        result = calculate_cpm_from_rate(Decimal("1000"), 50000)
        assert result == Decimal("20.00")
        assert result.as_tuple().exponent == -2


class TestDeriveCpmBounds:
    """Tests for campaign-aware CPM bound derivation."""

    def test_with_target_and_leniency(self):
        """CPM target $25, leniency 20% -> floor=$25, ceiling=$30."""
        floor, ceiling = derive_cpm_bounds(Decimal("25"), Decimal("20"))
        assert floor == Decimal("25.00")
        assert ceiling == Decimal("30.00")

    def test_with_target_no_leniency(self):
        """CPM target $25, leniency None -> floor=$25, ceiling=$25 (no room)."""
        floor, ceiling = derive_cpm_bounds(Decimal("25"), None)
        assert floor == Decimal("25.00")
        assert ceiling == Decimal("25.00")

    def test_with_target_zero_leniency(self):
        """CPM target $30, leniency 0% -> floor=$30, ceiling=$30."""
        floor, ceiling = derive_cpm_bounds(Decimal("30"), Decimal("0"))
        assert floor == Decimal("30.00")
        assert ceiling == Decimal("30.00")

    def test_with_target_100_leniency(self):
        """CPM target $20, leniency 100% -> floor=$20, ceiling=$40."""
        floor, ceiling = derive_cpm_bounds(Decimal("20"), Decimal("100"))
        assert floor == Decimal("20.00")
        assert ceiling == Decimal("40.00")

    def test_no_target_falls_back_to_defaults(self):
        """target None, leniency None -> module defaults ($20/$30)."""
        floor, ceiling = derive_cpm_bounds(None, None)
        assert floor == CPM_FLOOR
        assert ceiling == CPM_CEILING

    def test_no_target_with_leniency_ignored(self):
        """target None, leniency 50% -> defaults (leniency ignored without target)."""
        floor, ceiling = derive_cpm_bounds(None, Decimal("50"))
        assert floor == CPM_FLOOR
        assert ceiling == CPM_CEILING

    def test_decimal_precision(self):
        """Verify output is 2 decimal places."""
        floor, ceiling = derive_cpm_bounds(Decimal("25"), Decimal("20"))
        assert floor.as_tuple().exponent == -2
        assert ceiling.as_tuple().exponent == -2
