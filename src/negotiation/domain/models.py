"""Pydantic v2 models for domain data structures in the negotiation agent."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from negotiation.domain.types import (
    DeliverableType,
    NegotiationState,
    Platform,
    validate_platform_deliverable,
)


class PayRange(BaseModel):
    """Pre-calculated pay range based on influencer metrics.

    Represents the dollar amount range at the CPM floor ($20) and ceiling ($30).
    Uses Decimal for exact monetary arithmetic -- float inputs are rejected.
    """

    model_config = ConfigDict(frozen=True)

    min_rate: Decimal
    max_rate: Decimal
    average_views: int

    @field_validator("min_rate", "max_rate", mode="before")
    @classmethod
    def reject_float_inputs(cls, v: object) -> object:
        """Reject float inputs for monetary fields to prevent precision errors."""
        if isinstance(v, float):
            raise ValueError("Use Decimal or string, not float, for monetary values")
        return v

    @field_validator("average_views")
    @classmethod
    def views_must_be_positive(cls, v: int) -> int:
        """Ensure average_views is a positive integer."""
        if v <= 0:
            raise ValueError("average_views must be positive")
        return v

    @model_validator(mode="after")
    def min_rate_must_not_exceed_max_rate(self) -> "PayRange":
        """Ensure min_rate does not exceed max_rate."""
        if self.min_rate > self.max_rate:
            raise ValueError(
                f"min_rate ({self.min_rate}) must not exceed max_rate ({self.max_rate})"
            )
        return self


class Deliverable(BaseModel):
    """A specific content deliverable for an influencer campaign.

    Validates that the deliverable type is appropriate for the given platform.
    """

    model_config = ConfigDict(frozen=True)

    platform: Platform
    deliverable_type: DeliverableType
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        """Ensure quantity is at least 1."""
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v

    @model_validator(mode="after")
    def deliverable_type_must_match_platform(self) -> "Deliverable":
        """Ensure the deliverable type is valid for the given platform."""
        validate_platform_deliverable(self.platform, self.deliverable_type)
        return self


class NegotiationContext(BaseModel):
    """Full context for an influencer negotiation.

    Contains influencer info, deliverables, pay range, and current state.
    """

    influencer_name: str
    average_views: int
    deliverables: list[Deliverable]
    pay_range: PayRange
    current_state: NegotiationState = NegotiationState.INITIAL_OFFER
    notes: str | None = None

    @field_validator("influencer_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Ensure influencer_name is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("influencer_name must not be empty")
        return v

    @field_validator("average_views")
    @classmethod
    def views_must_be_positive(cls, v: int) -> int:
        """Ensure average_views is a positive integer."""
        if v <= 0:
            raise ValueError("average_views must be positive")
        return v

    @field_validator("deliverables")
    @classmethod
    def deliverables_must_not_be_empty(cls, v: list[Deliverable]) -> list[Deliverable]:
        """Ensure at least one deliverable is provided."""
        if len(v) == 0:
            raise ValueError("deliverables must not be empty")
        return v
