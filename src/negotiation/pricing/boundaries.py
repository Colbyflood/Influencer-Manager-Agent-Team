"""Rate boundary enforcement and escalation logic.

Evaluates proposed influencer rates against configurable CPM boundaries
to determine whether a rate is acceptable, requires escalation, or is
suspiciously low.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from negotiation.pricing.engine import (
    CPM_CEILING,
    CPM_FLOOR,
    calculate_cpm_from_rate,
)


class BoundaryResult(StrEnum):
    """Classification of a proposed rate relative to CPM boundaries."""

    WITHIN_RANGE = "within_range"
    EXCEEDS_CEILING = "exceeds_ceiling"
    BELOW_FLOOR = "below_floor"
    SUSPICIOUSLY_LOW = "suspiciously_low"


class PricingResult(BaseModel, frozen=True):
    """Result of evaluating a proposed rate against boundaries.

    Attributes:
        rate: The proposed rate that was evaluated.
        cpm: The implied CPM calculated from the rate and views.
        boundary: The boundary classification result.
        should_escalate: Whether this rate should be escalated to a human.
        warning: Optional warning message for problematic rates.
    """

    rate: Decimal
    cpm: Decimal
    boundary: BoundaryResult
    should_escalate: bool
    warning: str | None = None


def evaluate_proposed_rate(
    proposed_rate: Decimal,
    average_views: int,
    cpm_floor: Decimal = CPM_FLOOR,
    cpm_ceiling: Decimal = CPM_CEILING,
    low_rate_threshold: Decimal = Decimal("15"),
) -> PricingResult:
    """Evaluate a proposed rate against CPM boundaries.

    Determines whether the implied CPM from a proposed rate falls within
    acceptable boundaries, and whether escalation is needed.

    Boundary logic (evaluated in order):
    1. If implied CPM > ceiling: EXCEEDS_CEILING, should_escalate=True
    2. If implied CPM < low_rate_threshold: SUSPICIOUSLY_LOW
    3. If implied CPM < floor: BELOW_FLOOR
    4. Otherwise: WITHIN_RANGE

    Args:
        proposed_rate: The rate proposed by the influencer (in dollars).
        average_views: Average view count for the influencer's content.
        cpm_floor: Minimum acceptable CPM. Defaults to $20.
        cpm_ceiling: Maximum acceptable CPM. Defaults to $30.
        low_rate_threshold: CPM below this is flagged as suspiciously low.
            Defaults to $15.

    Returns:
        PricingResult with boundary classification, escalation flag, and
        optional warning message.

    Raises:
        PricingError: If average_views is zero or negative.
    """
    implied_cpm = calculate_cpm_from_rate(proposed_rate, average_views)

    if implied_cpm > cpm_ceiling:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.EXCEEDS_CEILING,
            should_escalate=True,
            warning=(
                f"Proposed rate implies ${implied_cpm} CPM, "
                f"which exceeds the ${cpm_ceiling} ceiling"
            ),
        )

    if implied_cpm < low_rate_threshold:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.SUSPICIOUSLY_LOW,
            should_escalate=False,
            warning=(
                f"Proposed rate implies ${implied_cpm} CPM, "
                f"which is suspiciously low (below ${low_rate_threshold} threshold)"
            ),
        )

    if implied_cpm < cpm_floor:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.BELOW_FLOOR,
            should_escalate=False,
        )

    return PricingResult(
        rate=proposed_rate,
        cpm=implied_cpm,
        boundary=BoundaryResult.WITHIN_RANGE,
        should_escalate=False,
    )
