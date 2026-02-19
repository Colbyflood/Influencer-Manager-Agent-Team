"""CPM-based rate calculation engine for influencer pricing.

All monetary calculations use Decimal arithmetic to avoid floating-point errors.
Rates are quantized to two decimal places with ROUND_HALF_UP rounding.
"""

from decimal import ROUND_HALF_UP, Decimal

from negotiation.domain.errors import PricingError

# Precision: all monetary values quantized to 2 decimal places
TWO_PLACES = Decimal("0.01")

# Default CPM boundaries (cost per mille / cost per thousand views)
CPM_FLOOR = Decimal("20")
CPM_CEILING = Decimal("30")


def _validate_views(average_views: int) -> None:
    """Validate that average_views is a positive integer.

    Args:
        average_views: The average view count to validate.

    Raises:
        PricingError: If average_views is zero or negative.
    """
    if average_views <= 0:
        raise PricingError(f"average_views must be positive, got {average_views}")


def calculate_rate(average_views: int, cpm: Decimal) -> Decimal:
    """Calculate the rate for given views and CPM.

    Formula: (average_views / 1000) * cpm, quantized to 2 decimal places.

    Args:
        average_views: Average view count for the influencer's content.
        cpm: Cost per thousand views (e.g., Decimal("20") for $20 CPM).

    Returns:
        The calculated rate as a Decimal with exactly 2 decimal places.

    Raises:
        PricingError: If average_views is zero or negative.
    """
    _validate_views(average_views)
    views_in_thousands = Decimal(average_views) / Decimal("1000")
    rate = views_in_thousands * cpm
    return rate.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_initial_offer(
    average_views: int,
    cpm_floor: Decimal = CPM_FLOOR,
) -> Decimal:
    """Calculate the initial offer for an influencer using the CPM floor.

    The initial offer represents the lowest reasonable rate based on
    the influencer's average views and the configurable CPM floor.

    Args:
        average_views: Average view count for the influencer's content.
        cpm_floor: The minimum acceptable CPM rate. Defaults to $20.

    Returns:
        The initial offer as a Decimal with exactly 2 decimal places.

    Raises:
        PricingError: If average_views is zero or negative.
    """
    return calculate_rate(average_views, cpm_floor)


def calculate_cpm_from_rate(rate: Decimal, average_views: int) -> Decimal:
    """Back-calculate the implied CPM from a proposed rate and view count.

    Formula: rate / (average_views / 1000), quantized to 2 decimal places.

    Args:
        rate: The proposed rate in dollars.
        average_views: Average view count for the influencer's content.

    Returns:
        The implied CPM as a Decimal with exactly 2 decimal places.

    Raises:
        PricingError: If average_views is zero or negative.
    """
    _validate_views(average_views)
    views_in_thousands = Decimal(average_views) / Decimal("1000")
    cpm = rate / views_in_thousands
    return cpm.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
