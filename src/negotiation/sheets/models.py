"""Pydantic v2 models for Google Sheets data.

Provides a frozen model for rows from the influencer tracking spreadsheet.
Handles the float-to-Decimal coercion needed because Google Sheets always
returns numeric values as floats.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from negotiation.domain.models import PayRange
from negotiation.domain.types import Platform


class InfluencerRow(BaseModel):
    """A single row from the influencer tracking Google Sheet.

    Coerces float values (as returned by the Sheets API) to ``Decimal``
    for monetary fields, preventing precision-loss errors when bridging
    to the ``PayRange`` domain model.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    email: str
    platform: Platform
    handle: str
    average_views: int
    min_rate: Decimal
    max_rate: Decimal
    engagement_rate: float | None = None

    @field_validator("min_rate", "max_rate", mode="before")
    @classmethod
    def coerce_from_sheet_float(cls, v: object) -> object:
        """Convert float values from Sheets to string before Decimal parsing.

        Google Sheets returns all numeric values as floats.  Converting
        float -> str -> Decimal preserves the displayed precision without
        triggering PayRange's float-rejection validator.
        """
        if isinstance(v, float):
            return str(v)
        return v

    @field_validator("average_views")
    @classmethod
    def views_must_be_positive(cls, v: int) -> int:
        """Ensure average_views is a positive integer."""
        if v <= 0:
            raise ValueError("average_views must be positive")
        return v

    def to_pay_range(self) -> PayRange:
        """Convert this row's rate data to a ``PayRange`` domain model.

        Returns:
            A ``PayRange`` with the same min/max rates and average views.
        """
        return PayRange(
            min_rate=self.min_rate,
            max_rate=self.max_rate,
            average_views=self.average_views,
        )
