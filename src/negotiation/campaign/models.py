"""Pydantic v2 models for campaign data sourced from ClickUp form submissions.

Validates all fields with Decimal precision for monetary values (no floats).
Imports Platform enum from domain types for consistency.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from negotiation.domain.types import Platform


class UsageRightsDuration(StrEnum):
    """Duration options for usage rights, ordered from shortest to longest."""

    not_required = "not_required"
    days_30 = "days_30"
    days_60 = "days_60"
    days_90 = "days_90"
    months_6 = "months_6"
    year_1 = "year_1"
    perpetual = "perpetual"


# Ordered list for comparison (index = severity)
_DURATION_ORDER = list(UsageRightsDuration)


class OptimizeFor(StrEnum):
    """What to optimize the campaign negotiation for."""

    cpm = "cpm"
    content_volume_usage_rights = "content_volume_usage_rights"
    balance = "balance"


class CampaignGoals(BaseModel):
    """Campaign goals and optimization targets."""

    model_config = ConfigDict(frozen=True)

    primary_goal: str
    secondary_goal: str | None = None
    business_context: str | None = None
    optimize_for: OptimizeFor = OptimizeFor.balance

    @field_validator("primary_goal")
    @classmethod
    def primary_goal_must_not_be_empty(cls, v: str) -> str:
        """Ensure primary goal is not empty."""
        if not v.strip():
            raise ValueError("primary_goal must not be empty")
        return v


class DeliverableScenarios(BaseModel):
    """Three tiers of deliverable scenarios for negotiation flexibility."""

    model_config = ConfigDict(frozen=True)

    target_deliverables: list[str]
    content_syndication: bool = False
    scenario_1: str | None = None
    scenario_2: str | None = None
    scenario_3: str | None = None

    @model_validator(mode="after")
    def at_least_one_scenario(self) -> "DeliverableScenarios":
        """At least one scenario must be provided."""
        if self.scenario_1 is None and self.scenario_2 is None and self.scenario_3 is None:
            raise ValueError("At least one deliverable scenario must be provided")
        return self


class UsageRightsSet(BaseModel):
    """A set of usage rights durations for paid, whitelisting, and organic."""

    model_config = ConfigDict(frozen=True)

    paid_usage: UsageRightsDuration = UsageRightsDuration.not_required
    whitelisting: UsageRightsDuration = UsageRightsDuration.not_required
    organic_owned: UsageRightsDuration = UsageRightsDuration.not_required


class UsageRights(BaseModel):
    """Target and minimum usage rights for negotiation."""

    model_config = ConfigDict(frozen=True)

    target: UsageRightsSet
    minimum: UsageRightsSet

    @model_validator(mode="after")
    def minimum_must_not_exceed_target(self) -> "UsageRights":
        """For each right type, minimum duration must not exceed target duration."""
        for field_name in ("paid_usage", "whitelisting", "organic_owned"):
            target_val = getattr(self.target, field_name)
            min_val = getattr(self.minimum, field_name)
            target_idx = _DURATION_ORDER.index(target_val)
            min_idx = _DURATION_ORDER.index(min_val)
            if min_idx > target_idx:
                raise ValueError(
                    f"minimum {field_name} ({min_val}) must not exceed "
                    f"target {field_name} ({target_val})"
                )
        return self


def _reject_float(v: object) -> object:
    """Reject float inputs to prevent precision errors on Decimal fields."""
    if isinstance(v, float):
        raise ValueError("Use Decimal or string, not float, for monetary values")
    return v


class BudgetConstraints(BaseModel):
    """Budget constraints and cost parameters for the campaign."""

    model_config = ConfigDict(frozen=True)

    campaign_budget: Decimal
    target_influencer_count: int | None = None
    target_cost_range: str | None = None
    min_cost_per_influencer: Decimal | None = None
    max_cost_without_approval: Decimal | None = None
    cpm_target: Decimal | None = None
    cpm_leniency_pct: Decimal | None = None

    @field_validator(
        "campaign_budget",
        "min_cost_per_influencer",
        "max_cost_without_approval",
        "cpm_target",
        "cpm_leniency_pct",
        mode="before",
    )
    @classmethod
    def reject_float_inputs(cls, v: object) -> object:
        """Reject float inputs for Decimal fields."""
        return _reject_float(v)


class ProductLeverage(BaseModel):
    """Product leverage information for negotiations."""

    model_config = ConfigDict(frozen=True)

    product_available: bool = False
    product_description: str | None = None
    product_monetary_value: Decimal | None = None

    @field_validator("product_monetary_value", mode="before")
    @classmethod
    def reject_float_inputs(cls, v: object) -> object:
        """Reject float inputs for monetary value."""
        return _reject_float(v)


class CampaignRequirements(BaseModel):
    """Additional campaign requirements for content and exclusivity."""

    model_config = ConfigDict(frozen=True)

    exclusivity_required: bool = False
    exclusivity_term: str | None = None
    exclusivity_description: str | None = None
    content_posted_organically: bool = False
    content_approval_required: bool = False
    revision_rounds: int = 0
    raw_footage_required: str | None = None
    content_delivery_date: str | None = None
    content_publish_date: str | None = None


class CampaignBackground(BaseModel):
    """Background information about the campaign client and logistics."""

    model_config = ConfigDict(frozen=True)

    client_website: str | None = None
    campaign_manager: str | None = None
    payment_methods: list[str] = []
    payment_terms: str | None = None


class DistributionInfo(BaseModel):
    """Distribution targets across platforms, markets, and influencer sizes."""

    model_config = ConfigDict(frozen=True)

    platform_distribution: str | None = None
    market_distribution: str | None = None
    influencer_size_distribution: str | None = None


class CampaignInfluencer(BaseModel):
    """An influencer assigned to a campaign.

    Tracks name, platform, and optional engagement rate for CPM flexibility.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    platform: Platform
    engagement_rate: float | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Ensure influencer name is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("name must not be empty")
        return v


class CampaignCPMRange(BaseModel):
    """Target CPM range for a campaign.

    Uses Decimal for exact monetary arithmetic -- float inputs are rejected.
    """

    model_config = ConfigDict(frozen=True)

    min_cpm: Decimal
    max_cpm: Decimal

    @field_validator("min_cpm", "max_cpm", mode="before")
    @classmethod
    def reject_float_inputs(cls, v: object) -> object:
        """Reject float inputs for CPM fields to prevent precision errors."""
        if isinstance(v, float):
            raise ValueError("Use Decimal or string, not float, for CPM values")
        return v

    @model_validator(mode="after")
    def min_must_not_exceed_max(self) -> "CampaignCPMRange":
        """Ensure min_cpm does not exceed max_cpm."""
        if self.min_cpm > self.max_cpm:
            raise ValueError(f"min_cpm ({self.min_cpm}) must not exceed max_cpm ({self.max_cpm})")
        return self


class Campaign(BaseModel):
    """A campaign sourced from ClickUp form submission.

    Contains all fields needed for campaign-level negotiation context:
    client info, budget, deliverables, influencer list, CPM range, and timeline.

    Expanded to support all 42 ClickUp form fields via structured sub-models.
    """

    model_config = ConfigDict(frozen=True)

    # Original fields (backward compatible)
    campaign_id: str = Field(description="ClickUp task ID")
    client_name: str
    budget: Decimal
    target_deliverables: str
    influencers: list[CampaignInfluencer] = []
    cpm_range: CampaignCPMRange
    platform: Platform
    timeline: str
    created_at: str = Field(description="ISO 8601 timestamp")

    # Expanded sub-models (all optional for backward compatibility)
    background: CampaignBackground | None = None
    goals: CampaignGoals | None = None
    deliverables: DeliverableScenarios | None = None
    usage_rights: UsageRights | None = None
    budget_constraints: BudgetConstraints | None = None
    product_leverage: ProductLeverage | None = None
    requirements: CampaignRequirements | None = None
    distribution: DistributionInfo | None = None

    @field_validator("budget", mode="before")
    @classmethod
    def reject_float_budget(cls, v: object) -> object:
        """Reject float inputs for budget to prevent precision errors."""
        if isinstance(v, float):
            raise ValueError("Use Decimal or string, not float, for budget")
        return v

    @field_validator("campaign_id", "client_name", "target_deliverables", "timeline")
    @classmethod
    def string_fields_must_not_be_empty(cls, v: str) -> str:
        """Ensure required string fields are not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("field must not be empty")
        return v
