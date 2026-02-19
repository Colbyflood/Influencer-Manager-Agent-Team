"""Shared pytest fixtures for the negotiation agent test suite."""

from decimal import Decimal

import pytest

from negotiation.domain.models import Deliverable, NegotiationContext, PayRange
from negotiation.domain.types import DeliverableType, Platform


@pytest.fixture
def sample_pay_range() -> PayRange:
    """A representative pay range for testing."""
    return PayRange(
        min_rate=Decimal("1000"),
        max_rate=Decimal("1500"),
        average_views=50000,
    )


@pytest.fixture
def sample_deliverable() -> Deliverable:
    """A representative Instagram Reel deliverable for testing."""
    return Deliverable(
        platform=Platform.INSTAGRAM,
        deliverable_type=DeliverableType.INSTAGRAM_REEL,
    )


@pytest.fixture
def sample_context(
    sample_pay_range: PayRange, sample_deliverable: Deliverable
) -> NegotiationContext:
    """A representative negotiation context for testing."""
    return NegotiationContext(
        influencer_name="Test Influencer",
        average_views=50000,
        deliverables=[sample_deliverable],
        pay_range=sample_pay_range,
    )
