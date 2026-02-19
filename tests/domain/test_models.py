"""Tests for Pydantic domain models: PayRange, Deliverable, NegotiationContext."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from negotiation.domain.models import Deliverable, NegotiationContext, PayRange
from negotiation.domain.types import DeliverableType, NegotiationState, Platform


class TestPayRange:
    """Tests for the PayRange model."""

    def test_valid_creation_with_decimal_strings(self):
        pr = PayRange(min_rate=Decimal("1000"), max_rate=Decimal("1500"), average_views=50000)
        assert pr.min_rate == Decimal("1000")
        assert pr.max_rate == Decimal("1500")
        assert pr.average_views == 50000

    def test_valid_creation_with_string_inputs(self):
        """Pydantic should coerce string inputs to Decimal."""
        pr = PayRange(min_rate="800", max_rate="1200", average_views=40000)
        assert pr.min_rate == Decimal("800")
        assert pr.max_rate == Decimal("1200")

    def test_rejects_float_min_rate(self):
        with pytest.raises(ValidationError, match="Use Decimal or string, not float"):
            PayRange(min_rate=1000.0, max_rate=Decimal("1500"), average_views=50000)

    def test_rejects_float_max_rate(self):
        with pytest.raises(ValidationError, match="Use Decimal or string, not float"):
            PayRange(min_rate=Decimal("1000"), max_rate=1500.0, average_views=50000)

    def test_rejects_negative_average_views(self):
        with pytest.raises(ValidationError, match="average_views must be positive"):
            PayRange(min_rate=Decimal("1000"), max_rate=Decimal("1500"), average_views=-100)

    def test_rejects_zero_average_views(self):
        with pytest.raises(ValidationError, match="average_views must be positive"):
            PayRange(min_rate=Decimal("1000"), max_rate=Decimal("1500"), average_views=0)

    def test_rejects_min_rate_exceeding_max_rate(self):
        with pytest.raises(ValidationError, match="must not exceed"):
            PayRange(min_rate=Decimal("2000"), max_rate=Decimal("1500"), average_views=50000)

    def test_equal_min_and_max_rate_is_valid(self):
        pr = PayRange(min_rate=Decimal("1000"), max_rate=Decimal("1000"), average_views=50000)
        assert pr.min_rate == pr.max_rate

    def test_frozen_immutability(self):
        pr = PayRange(min_rate=Decimal("1000"), max_rate=Decimal("1500"), average_views=50000)
        with pytest.raises(ValidationError):
            pr.min_rate = Decimal("999")  # type: ignore[misc]

    def test_serialization_round_trip(self):
        original = PayRange(min_rate=Decimal("1000"), max_rate=Decimal("1500"), average_views=50000)
        data = original.model_dump()
        restored = PayRange.model_validate(data)
        assert restored == original


class TestDeliverable:
    """Tests for the Deliverable model."""

    def test_valid_creation(self):
        d = Deliverable(
            platform=Platform.INSTAGRAM,
            deliverable_type=DeliverableType.INSTAGRAM_REEL,
        )
        assert d.platform == Platform.INSTAGRAM
        assert d.deliverable_type == DeliverableType.INSTAGRAM_REEL
        assert d.quantity == 1

    def test_custom_quantity(self):
        d = Deliverable(
            platform=Platform.TIKTOK,
            deliverable_type=DeliverableType.TIKTOK_VIDEO,
            quantity=3,
        )
        assert d.quantity == 3

    def test_rejects_mismatched_platform_deliverable(self):
        with pytest.raises(ValidationError, match="is not valid for"):
            Deliverable(
                platform=Platform.YOUTUBE,
                deliverable_type=DeliverableType.INSTAGRAM_REEL,
            )

    def test_rejects_zero_quantity(self):
        with pytest.raises(ValidationError, match="quantity must be at least 1"):
            Deliverable(
                platform=Platform.INSTAGRAM,
                deliverable_type=DeliverableType.INSTAGRAM_POST,
                quantity=0,
            )

    def test_rejects_negative_quantity(self):
        with pytest.raises(ValidationError, match="quantity must be at least 1"):
            Deliverable(
                platform=Platform.INSTAGRAM,
                deliverable_type=DeliverableType.INSTAGRAM_POST,
                quantity=-1,
            )

    def test_frozen_immutability(self):
        d = Deliverable(
            platform=Platform.INSTAGRAM,
            deliverable_type=DeliverableType.INSTAGRAM_POST,
        )
        with pytest.raises(ValidationError):
            d.quantity = 5  # type: ignore[misc]

    def test_all_valid_platform_deliverable_pairs(self):
        """Ensure all valid platform-deliverable pairs can create Deliverable instances."""
        valid_pairs = [
            (Platform.INSTAGRAM, DeliverableType.INSTAGRAM_POST),
            (Platform.INSTAGRAM, DeliverableType.INSTAGRAM_STORY),
            (Platform.INSTAGRAM, DeliverableType.INSTAGRAM_REEL),
            (Platform.TIKTOK, DeliverableType.TIKTOK_VIDEO),
            (Platform.TIKTOK, DeliverableType.TIKTOK_STORY),
            (Platform.YOUTUBE, DeliverableType.YOUTUBE_DEDICATED),
            (Platform.YOUTUBE, DeliverableType.YOUTUBE_INTEGRATION),
            (Platform.YOUTUBE, DeliverableType.YOUTUBE_SHORT),
        ]
        for platform, dt in valid_pairs:
            d = Deliverable(platform=platform, deliverable_type=dt)
            assert d.platform == platform
            assert d.deliverable_type == dt

    def test_serialization_round_trip(self):
        original = Deliverable(
            platform=Platform.INSTAGRAM,
            deliverable_type=DeliverableType.INSTAGRAM_REEL,
            quantity=2,
        )
        data = original.model_dump()
        restored = Deliverable.model_validate(data)
        assert restored == original


class TestNegotiationContext:
    """Tests for the NegotiationContext model."""

    def test_valid_creation(self, sample_pay_range, sample_deliverable):
        ctx = NegotiationContext(
            influencer_name="Test Creator",
            average_views=50000,
            deliverables=[sample_deliverable],
            pay_range=sample_pay_range,
        )
        assert ctx.influencer_name == "Test Creator"
        assert ctx.average_views == 50000
        assert ctx.current_state == NegotiationState.INITIAL_OFFER
        assert ctx.notes is None

    def test_custom_state_and_notes(self, sample_pay_range, sample_deliverable):
        ctx = NegotiationContext(
            influencer_name="Test Creator",
            average_views=50000,
            deliverables=[sample_deliverable],
            pay_range=sample_pay_range,
            current_state=NegotiationState.COUNTER_RECEIVED,
            notes="Influencer wants higher rate",
        )
        assert ctx.current_state == NegotiationState.COUNTER_RECEIVED
        assert ctx.notes == "Influencer wants higher rate"

    def test_rejects_empty_influencer_name(self, sample_pay_range, sample_deliverable):
        with pytest.raises(ValidationError, match="influencer_name must not be empty"):
            NegotiationContext(
                influencer_name="",
                average_views=50000,
                deliverables=[sample_deliverable],
                pay_range=sample_pay_range,
            )

    def test_rejects_whitespace_only_name(self, sample_pay_range, sample_deliverable):
        with pytest.raises(ValidationError, match="influencer_name must not be empty"):
            NegotiationContext(
                influencer_name="   ",
                average_views=50000,
                deliverables=[sample_deliverable],
                pay_range=sample_pay_range,
            )

    def test_rejects_zero_average_views(self, sample_pay_range, sample_deliverable):
        with pytest.raises(ValidationError, match="average_views must be positive"):
            NegotiationContext(
                influencer_name="Test Creator",
                average_views=0,
                deliverables=[sample_deliverable],
                pay_range=sample_pay_range,
            )

    def test_rejects_empty_deliverables(self, sample_pay_range):
        with pytest.raises(ValidationError, match="deliverables must not be empty"):
            NegotiationContext(
                influencer_name="Test Creator",
                average_views=50000,
                deliverables=[],
                pay_range=sample_pay_range,
            )

    def test_serialization_round_trip(self, sample_pay_range, sample_deliverable):
        original = NegotiationContext(
            influencer_name="Round Trip Creator",
            average_views=75000,
            deliverables=[sample_deliverable],
            pay_range=sample_pay_range,
            notes="Testing serialization",
        )
        data = original.model_dump()
        restored = NegotiationContext.model_validate(data)
        assert restored.influencer_name == original.influencer_name
        assert restored.average_views == original.average_views
        assert restored.current_state == original.current_state
        assert restored.notes == original.notes
        assert len(restored.deliverables) == len(original.deliverables)

    def test_with_fixture(self, sample_context):
        """Test that the shared sample_context fixture works correctly."""
        assert sample_context.influencer_name == "Test Influencer"
        assert sample_context.average_views == 50000
        assert len(sample_context.deliverables) == 1
        assert sample_context.current_state == NegotiationState.INITIAL_OFFER
