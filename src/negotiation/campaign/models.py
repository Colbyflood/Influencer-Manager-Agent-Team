"""Pydantic v2 models for campaign data sourced from ClickUp form submissions.

Validates all fields with Decimal precision for monetary values (no floats).
Imports Platform enum from domain types for consistency.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from negotiation.domain.types import Platform


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
    """

    model_config = ConfigDict(frozen=True)

    campaign_id: str = Field(description="ClickUp task ID")
    client_name: str
    budget: Decimal
    target_deliverables: str
    influencers: list[CampaignInfluencer]
    cpm_range: CampaignCPMRange
    platform: Platform
    timeline: str
    created_at: str = Field(description="ISO 8601 timestamp")

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

    @field_validator("influencers")
    @classmethod
    def must_have_at_least_one_influencer(
        cls,
        v: list[CampaignInfluencer],
    ) -> list[CampaignInfluencer]:
        """Ensure at least one influencer is assigned to the campaign."""
        if len(v) == 0:
            raise ValueError("campaign must have at least one influencer")
        return v
