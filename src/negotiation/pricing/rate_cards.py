"""Platform-specific rate cards and deliverable pricing.

Each deliverable type has an associated RateCard that defines the CPM floor
and ceiling for that type. For v1, all deliverable types share the same
$20-$30 CPM range, but the architecture supports per-type customization.
"""

from decimal import Decimal

from pydantic import BaseModel

from negotiation.domain.types import DeliverableType
from negotiation.pricing.engine import CPM_CEILING, CPM_FLOOR, calculate_rate


class RateCard(BaseModel, frozen=True):
    """Immutable rate card for a deliverable type.

    Attributes:
        deliverable_type: The deliverable type this card applies to.
        cpm_floor: Minimum CPM for this deliverable type.
        cpm_ceiling: Maximum CPM for this deliverable type.
    """

    deliverable_type: DeliverableType
    cpm_floor: Decimal = CPM_FLOOR
    cpm_ceiling: Decimal = CPM_CEILING


# Default rate cards for all deliverable types (v1: uniform $20-$30 CPM range)
DEFAULT_RATE_CARDS: dict[DeliverableType, RateCard] = {
    dt: RateCard(deliverable_type=dt) for dt in DeliverableType
}


def get_rate_card(deliverable_type: DeliverableType) -> RateCard:
    """Look up the rate card for a deliverable type.

    Args:
        deliverable_type: The deliverable type to look up.

    Returns:
        The RateCard for the given deliverable type.
    """
    return DEFAULT_RATE_CARDS[deliverable_type]


def calculate_deliverable_rate(
    deliverable_type: DeliverableType,
    average_views: int,
    cpm: Decimal | None = None,
) -> Decimal:
    """Calculate the rate for a specific deliverable type.

    Uses the rate card's CPM floor if no CPM is provided.

    Args:
        deliverable_type: The type of deliverable being priced.
        average_views: Average view count for the influencer's content.
        cpm: Optional CPM override. If None, uses the rate card's cpm_floor.

    Returns:
        The calculated rate as a Decimal with exactly 2 decimal places.

    Raises:
        PricingError: If average_views is zero or negative.
    """
    card = get_rate_card(deliverable_type)
    effective_cpm = cpm if cpm is not None else card.cpm_floor
    return calculate_rate(average_views, effective_cpm)
