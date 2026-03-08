"""Data models for the negotiation lever engine.

Defines lever actions (what tactic to use), negotiation context (current state),
and lever results (what the engine decided). All models are frozen for immutability.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from negotiation.campaign.models import (
    BudgetConstraints,
    DeliverableScenarios,
    ProductLeverage,
    UsageRights,
)


class LeverAction(StrEnum):
    """Negotiation lever actions mapped to NEG requirements."""

    open_high = "open_high"  # NEG-08: open with scenario_1 and floor CPM
    trade_deliverables = "trade_deliverables"  # NEG-09: downgrade deliverable tier
    trade_usage_rights = "trade_usage_rights"  # NEG-10: reduce usage rights duration
    offer_product = "offer_product"  # NEG-11: add product/upgrade value
    propose_syndication = "propose_syndication"  # NEG-14: cross-post instead of unique
    share_cpm_target = "share_cpm_target"  # NEG-13: reveal CPM target to justify budget
    enforce_floor = "enforce_floor"  # NEG-12: at min_cost, cannot go lower
    escalate_ceiling = "escalate_ceiling"  # NEG-12: rate exceeds max_cost_without_approval
    graceful_exit = "graceful_exit"  # NEG-15: all levers exhausted, exit


class NegotiationLeverContext(BaseModel):
    """Current state of a negotiation for lever selection.

    Captures the influencer's rate, our rate, campaign data, and which
    levers have already been used in this negotiation.
    """

    model_config = ConfigDict(frozen=True)

    their_rate: Decimal
    our_current_rate: Decimal
    average_views: int
    current_scenario: int  # which deliverable tier (1, 2, or 3)
    current_usage_tier: str  # "target" or "minimum"
    product_offered: bool
    syndication_proposed: bool
    cpm_shared: bool
    round_number: int
    deliverable_scenarios: DeliverableScenarios | None = None
    usage_rights: UsageRights | None = None
    budget_constraints: BudgetConstraints | None = None
    product_leverage: ProductLeverage | None = None


class LeverResult(BaseModel):
    """Result of lever selection -- what action to take and how to frame it.

    The lever_instructions field contains natural language guidance for the
    LLM email composer describing how to frame the chosen tactic.
    """

    model_config = ConfigDict(frozen=True)

    action: LeverAction
    adjusted_rate: Decimal | None = None
    deliverables_summary: str | None = None
    usage_rights_summary: str | None = None
    lever_instructions: str
    should_escalate: bool = False
    should_exit: bool = False
