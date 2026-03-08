"""Data models for counterparty detection and classification.

Provides the core types used by the classifier to represent detection
results: what type of counterparty was detected, with what confidence,
and which signals contributed to the classification.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CounterpartyType(StrEnum):
    """The type of counterparty in a negotiation."""

    DIRECT_INFLUENCER = "direct_influencer"
    TALENT_MANAGER = "talent_manager"


class DetectionSignal(BaseModel):
    """A single signal contributing to counterparty classification.

    Each signal represents one piece of evidence (e.g., an agency domain,
    a title keyword in the signature) that points toward a particular
    counterparty type.
    """

    model_config = ConfigDict(frozen=True)

    signal_type: str  # e.g. "agency_domain", "signature_title", "email_structure"
    value: str  # the matched text
    strength: float  # 0.0 - 1.0
    indicates: CounterpartyType


class CounterpartyProfile(BaseModel):
    """The result of classifying an email sender.

    Contains the detected counterparty type, the confidence level,
    all signals that contributed, and optional extracted metadata
    (agency name, contact name, contact title).
    """

    model_config = ConfigDict(frozen=True)

    counterparty_type: CounterpartyType
    confidence: float
    signals: list[DetectionSignal]
    agency_name: str | None = None
    contact_name: str | None = None
    contact_title: str | None = None
