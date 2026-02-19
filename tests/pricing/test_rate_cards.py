"""Tests for platform-specific rate cards and deliverable pricing."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from negotiation.domain.types import DeliverableType
from negotiation.pricing.rate_cards import (
    RateCard,
    calculate_deliverable_rate,
    get_rate_card,
)


class TestRateCard:
    """Tests for the RateCard model."""

    def test_rate_card_has_default_cpm_floor(self):
        card = get_rate_card(DeliverableType.INSTAGRAM_REEL)
        assert card.cpm_floor == Decimal("20")

    def test_rate_card_has_default_cpm_ceiling(self):
        card = get_rate_card(DeliverableType.INSTAGRAM_REEL)
        assert card.cpm_ceiling == Decimal("30")

    def test_rate_card_is_frozen(self):
        card = get_rate_card(DeliverableType.INSTAGRAM_REEL)
        with pytest.raises(ValidationError):
            card.cpm_floor = Decimal("99")  # type: ignore[misc]


class TestCalculateDeliverableRate:
    """Tests for deliverable-specific rate calculation."""

    @pytest.mark.parametrize(
        "deliverable_type",
        list(DeliverableType),
        ids=[dt.value for dt in DeliverableType],
    )
    def test_all_deliverable_types_produce_valid_rates(self, deliverable_type: DeliverableType):
        """Every deliverable type must return a positive Decimal rate."""
        rate = calculate_deliverable_rate(deliverable_type, 50000)
        assert isinstance(rate, Decimal)
        assert rate > Decimal("0")

    def test_deliverable_rate_uses_cpm_floor_by_default(self):
        rate = calculate_deliverable_rate(DeliverableType.INSTAGRAM_REEL, 50000)
        # 50000 / 1000 * $20 = $1000
        assert rate == Decimal("1000.00")

    def test_deliverable_rate_with_custom_cpm(self):
        rate = calculate_deliverable_rate(DeliverableType.INSTAGRAM_REEL, 50000, cpm=Decimal("25"))
        assert rate == Decimal("1250.00")

    def test_deliverable_rate_uses_decimal_arithmetic(self):
        rate = calculate_deliverable_rate(DeliverableType.TIKTOK_VIDEO, 50000)
        assert isinstance(rate, Decimal)
        assert rate.as_tuple().exponent == -2

    def test_rate_card_accepts_configurable_cpm_parameters(self):
        """Rate cards with custom floor/ceiling are valid."""
        card = RateCard(
            deliverable_type=DeliverableType.YOUTUBE_DEDICATED,
            cpm_floor=Decimal("25"),
            cpm_ceiling=Decimal("40"),
        )
        assert card.cpm_floor == Decimal("25")
        assert card.cpm_ceiling == Decimal("40")
