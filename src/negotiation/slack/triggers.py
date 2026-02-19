"""Escalation trigger engine for configurable rule-based email evaluation.

Combines deterministic triggers (CPM threshold, ambiguous intent) with
LLM-based triggers (hostile tone, legal language, unusual deliverables).
Loads trigger configuration from YAML files validated via Pydantic.

The trigger engine runs as a pre-processing gate before the negotiation loop,
catching emails that should be escalated before any autonomous response.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from anthropic import Anthropic
from pydantic import BaseModel, Field

from negotiation.llm.client import DEFAULT_CONFIDENCE_THRESHOLD, INTENT_MODEL

logger = logging.getLogger(__name__)


class TriggerType(StrEnum):
    """Types of escalation triggers."""

    CPM_OVER_THRESHOLD = "cpm_over_threshold"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    HOSTILE_TONE = "hostile_tone"
    LEGAL_LANGUAGE = "legal_language"
    UNUSUAL_DELIVERABLES = "unusual_deliverables"


class TriggerConfig(BaseModel):
    """Configuration for a single escalation trigger."""

    enabled: bool = True
    # For CPM trigger
    cpm_threshold: float | None = None
    # For LLM-based triggers: optional keywords that always trigger (bypass LLM)
    always_trigger_keywords: list[str] = Field(default_factory=list)


class EscalationTriggersConfig(BaseModel):
    """Root configuration for all escalation triggers.

    Loaded from YAML config file and validated by Pydantic.
    All triggers enabled by default with CPM threshold of 30.0.
    """

    cpm_over_threshold: TriggerConfig = Field(
        default_factory=lambda: TriggerConfig(cpm_threshold=30.0)
    )
    ambiguous_intent: TriggerConfig = Field(default_factory=TriggerConfig)
    hostile_tone: TriggerConfig = Field(default_factory=TriggerConfig)
    legal_language: TriggerConfig = Field(default_factory=TriggerConfig)
    unusual_deliverables: TriggerConfig = Field(default_factory=TriggerConfig)


class TriggerResult(BaseModel):
    """Result of evaluating a single trigger."""

    trigger_type: TriggerType
    fired: bool
    reason: str = ""
    evidence: str = ""


class TriggerClassification(BaseModel):
    """Structured output for LLM-based trigger detection.

    Used with Anthropic structured outputs (client.messages.parse()) to
    classify an email for hostile tone, legal language, and unusual deliverables
    in a single API call.
    """

    hostile_tone_detected: bool = Field(
        description="True if the email contains hostile, aggressive, or threatening language"
    )
    hostile_evidence: str = Field(
        default="",
        description="Quote from the email that demonstrates hostile tone. Empty if not detected.",
    )
    legal_language_detected: bool = Field(
        description="True if the email contains legal or contract-related language"
    )
    legal_evidence: str = Field(
        default="",
        description=(
            "Quote from the email demonstrating legal/contract language. Empty if not detected."
        ),
    )
    unusual_deliverables_detected: bool = Field(
        description="True if the email requests unusual or non-standard deliverables"
    )
    unusual_evidence: str = Field(
        default="",
        description="Quote describing the unusual deliverable request. Empty if not detected.",
    )


DEFAULT_TRIGGERS_PATH = Path(__file__).resolve().parents[3] / "config" / "escalation_triggers.yaml"

_TRIGGER_CLASSIFICATION_SYSTEM_PROMPT = """\
Analyze this influencer email for three escalation triggers:

1. HOSTILE TONE: Aggressive, threatening, condescending, or hostile language.
   Examples: threats to go public, demands with ultimatums, insults, passive-aggressive remarks.
   NOT hostile: firm negotiation, simple disagreement, declining an offer politely.

2. LEGAL/CONTRACT LANGUAGE: References to contracts, lawyers, legal action, terms and conditions,
   NDAs, exclusivity clauses, intellectual property, licensing, or legal representatives.
   NOT legal: casual mention of "deal" or "agreement" in normal negotiation context.

3. UNUSUAL DELIVERABLES: Requests for deliverables outside standard platform content
   (posts, stories, reels, videos, shorts). Examples: event appearances, product design
   input, long-term ambassadorship, content licensing, whitelisting/paid ads with their content.
   NOT unusual: standard platform deliverables even if quantity is high.

For each trigger, quote the SPECIFIC text from the email that triggered the detection.
If not detected, leave evidence empty."""


def load_triggers_config(
    path: Path = DEFAULT_TRIGGERS_PATH,
) -> EscalationTriggersConfig:
    """Load and validate escalation trigger config from YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        Validated config. Falls back to all-defaults if file is missing,
        empty, or contains invalid YAML.
    """
    if not path.exists():
        return EscalationTriggersConfig()

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        logger.warning("Invalid YAML in %s, using defaults", path)
        return EscalationTriggersConfig()

    if raw is None:
        return EscalationTriggersConfig()

    return EscalationTriggersConfig.model_validate(raw)


def classify_triggers(
    email_body: str,
    client: Anthropic,
    model: str = INTENT_MODEL,
) -> TriggerClassification:
    """Classify an email for tone, legal, and deliverable triggers.

    Uses Claude Haiku structured outputs for fast, cheap classification.
    This runs BEFORE the main intent classification to catch escalation
    triggers early.

    Args:
        email_body: The influencer email body text.
        client: Anthropic API client.
        model: Model to use for classification.

    Returns:
        TriggerClassification with bool + evidence for each LLM trigger.

    Raises:
        RuntimeError: If the LLM returns None parsed_output.
    """
    response = client.messages.parse(
        model=model,
        max_tokens=512,
        system=_TRIGGER_CLASSIFICATION_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Analyze this email:\n\n{email_body}"},
        ],
        output_format=TriggerClassification,
    )

    parsed = response.parsed_output
    if parsed is None:
        raise RuntimeError("Trigger classification returned None")
    return parsed


def evaluate_triggers(
    email_body: str,
    proposed_cpm: float,
    intent_confidence: float,
    config: EscalationTriggersConfig,
    client: Anthropic | None,
) -> list[TriggerResult]:
    """Evaluate all enabled triggers against an influencer email.

    Checks deterministic triggers first (no API cost), then calls
    classify_triggers for LLM-based triggers only if needed.

    Args:
        email_body: The influencer email body text.
        proposed_cpm: The calculated CPM from the proposed rate and average views.
        intent_confidence: Confidence score from intent classification (0.0-1.0).
        config: Escalation trigger configuration.
        client: Anthropic API client (None skips LLM triggers).

    Returns:
        List of fired TriggerResults. Empty list means no escalation needed.
    """
    results: list[TriggerResult] = []

    # Deterministic trigger 1: CPM over threshold
    if config.cpm_over_threshold.enabled:
        threshold = config.cpm_over_threshold.cpm_threshold or 30.0
        if proposed_cpm > threshold:
            results.append(
                TriggerResult(
                    trigger_type=TriggerType.CPM_OVER_THRESHOLD,
                    fired=True,
                    reason=f"CPM ${proposed_cpm:.2f} exceeds threshold ${threshold:.2f}",
                )
            )

    # Deterministic trigger 2: Ambiguous intent
    if config.ambiguous_intent.enabled and intent_confidence < DEFAULT_CONFIDENCE_THRESHOLD:
        results.append(
            TriggerResult(
                trigger_type=TriggerType.AMBIGUOUS_INTENT,
                fired=True,
                reason=f"Intent confidence {intent_confidence:.2f} below threshold",
            )
        )

    # LLM-based triggers (only if at least one is enabled and client is available)
    llm_triggers_enabled = (
        config.hostile_tone.enabled
        or config.legal_language.enabled
        or config.unusual_deliverables.enabled
    )

    if llm_triggers_enabled and client is not None:
        classification = classify_triggers(email_body, client)

        # Hostile tone
        if config.hostile_tone.enabled and classification.hostile_tone_detected:
            results.append(
                TriggerResult(
                    trigger_type=TriggerType.HOSTILE_TONE,
                    fired=True,
                    reason="Hostile tone detected in email",
                    evidence=classification.hostile_evidence,
                )
            )

        # Legal language
        if config.legal_language.enabled and classification.legal_language_detected:
            results.append(
                TriggerResult(
                    trigger_type=TriggerType.LEGAL_LANGUAGE,
                    fired=True,
                    reason="Legal/contract language detected in email",
                    evidence=classification.legal_evidence,
                )
            )

        # Unusual deliverables
        if config.unusual_deliverables.enabled and classification.unusual_deliverables_detected:
            results.append(
                TriggerResult(
                    trigger_type=TriggerType.UNUSUAL_DELIVERABLES,
                    fired=True,
                    reason="Unusual deliverable request detected in email",
                    evidence=classification.unusual_evidence,
                )
            )

    return results
