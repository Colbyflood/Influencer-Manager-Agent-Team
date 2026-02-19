"""Pricing engine for CPM-based rate calculations.

Re-exports key functions and types for convenient access:
    from negotiation.pricing import calculate_rate, evaluate_proposed_rate, BoundaryResult
"""

from negotiation.pricing.boundaries import (
    BoundaryResult,
    PricingResult,
    evaluate_proposed_rate,
)
from negotiation.pricing.engine import (
    CPM_CEILING,
    CPM_FLOOR,
    calculate_cpm_from_rate,
    calculate_initial_offer,
    calculate_rate,
)
from negotiation.pricing.rate_cards import (
    RateCard,
    calculate_deliverable_rate,
    get_rate_card,
)

__all__ = [
    "CPM_CEILING",
    "CPM_FLOOR",
    "BoundaryResult",
    "PricingResult",
    "RateCard",
    "calculate_cpm_from_rate",
    "calculate_deliverable_rate",
    "calculate_initial_offer",
    "calculate_rate",
    "evaluate_proposed_rate",
    "get_rate_card",
]
