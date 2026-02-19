"""Tests for the sheets domain models."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from negotiation.domain.models import PayRange
from negotiation.sheets.models import InfluencerRow


class TestInfluencerRow:
    """Tests for InfluencerRow model."""

    def _make(self, **overrides) -> InfluencerRow:
        defaults = {
            "name": "Jane Creator",
            "email": "jane@example.com",
            "platform": "instagram",
            "handle": "@janecreator",
            "average_views": 50000,
            "min_rate": "1000.00",
            "max_rate": "1500.00",
        }
        defaults.update(overrides)
        return InfluencerRow(**defaults)

    # --- Creation & basic validation ---

    def test_create_valid(self):
        """Creates an InfluencerRow with valid data."""
        row = self._make()
        assert row.name == "Jane Creator"
        assert row.email == "jane@example.com"
        assert row.platform.value == "instagram"
        assert row.handle == "@janecreator"
        assert row.average_views == 50000
        assert row.min_rate == Decimal("1000.00")
        assert row.max_rate == Decimal("1500.00")

    def test_frozen_immutability(self):
        """Cannot mutate fields on a frozen model."""
        row = self._make()
        with pytest.raises(ValidationError):
            row.name = "changed"

    # --- Float coercion ---

    def test_float_coercion_min_rate(self):
        """Float min_rate is coerced to Decimal via string conversion."""
        row = self._make(min_rate=1000.0)
        assert isinstance(row.min_rate, Decimal)
        assert row.min_rate == Decimal("1000.0")

    def test_float_coercion_max_rate(self):
        """Float max_rate is coerced to Decimal via string conversion."""
        row = self._make(max_rate=1500.50)
        assert isinstance(row.max_rate, Decimal)
        assert row.max_rate == Decimal("1500.5")

    def test_float_coercion_both_rates(self):
        """Both rates coerced correctly when passed as floats."""
        row = self._make(min_rate=999.99, max_rate=2000.0)
        assert isinstance(row.min_rate, Decimal)
        assert isinstance(row.max_rate, Decimal)

    def test_string_rate_passthrough(self):
        """String rates pass through to Decimal without coercion issues."""
        row = self._make(min_rate="500.25", max_rate="750.75")
        assert row.min_rate == Decimal("500.25")
        assert row.max_rate == Decimal("750.75")

    def test_decimal_rate_passthrough(self):
        """Decimal rates pass through unchanged."""
        row = self._make(min_rate=Decimal("800"), max_rate=Decimal("1200"))
        assert row.min_rate == Decimal("800")
        assert row.max_rate == Decimal("1200")

    # --- views_must_be_positive ---

    def test_views_must_be_positive_rejects_zero(self):
        """Rejects average_views of 0."""
        with pytest.raises(ValidationError, match="average_views must be positive"):
            self._make(average_views=0)

    def test_views_must_be_positive_rejects_negative(self):
        """Rejects negative average_views."""
        with pytest.raises(ValidationError, match="average_views must be positive"):
            self._make(average_views=-100)

    def test_views_accepts_positive(self):
        """Accepts positive average_views."""
        row = self._make(average_views=1)
        assert row.average_views == 1

    # --- Platform validation ---

    def test_platform_instagram(self):
        """Accepts 'instagram' as platform."""
        row = self._make(platform="instagram")
        assert row.platform.value == "instagram"

    def test_platform_tiktok(self):
        """Accepts 'tiktok' as platform."""
        row = self._make(platform="tiktok")
        assert row.platform.value == "tiktok"

    def test_platform_youtube(self):
        """Accepts 'youtube' as platform."""
        row = self._make(platform="youtube")
        assert row.platform.value == "youtube"

    def test_platform_invalid(self):
        """Rejects invalid platform values."""
        with pytest.raises(ValidationError):
            self._make(platform="twitter")

    # --- to_pay_range ---

    def test_to_pay_range_returns_pay_range(self):
        """to_pay_range returns a PayRange domain model."""
        row = self._make()
        pay_range = row.to_pay_range()
        assert isinstance(pay_range, PayRange)

    def test_to_pay_range_correct_values(self):
        """to_pay_range maps fields correctly."""
        row = self._make(min_rate="1000", max_rate="1500", average_views=50000)
        pay_range = row.to_pay_range()
        assert pay_range.min_rate == Decimal("1000")
        assert pay_range.max_rate == Decimal("1500")
        assert pay_range.average_views == 50000

    def test_to_pay_range_with_float_coercion(self):
        """to_pay_range works correctly after float coercion."""
        row = self._make(min_rate=1000.0, max_rate=1500.0)
        pay_range = row.to_pay_range()
        assert isinstance(pay_range.min_rate, Decimal)
        assert isinstance(pay_range.max_rate, Decimal)

    # --- engagement_rate ---

    def test_engagement_rate_defaults_to_none(self):
        """engagement_rate defaults to None when not provided."""
        row = self._make()
        assert row.engagement_rate is None

    def test_engagement_rate_accepts_float(self):
        """engagement_rate accepts a float value."""
        row = self._make(engagement_rate=4.5)
        assert row.engagement_rate == 4.5

    def test_engagement_rate_accepts_none_explicitly(self):
        """engagement_rate accepts None when passed explicitly."""
        row = self._make(engagement_rate=None)
        assert row.engagement_rate is None
