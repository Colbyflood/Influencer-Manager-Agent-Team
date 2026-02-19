"""Tests for the escalation trigger engine.

Tests config loading (YAML + Pydantic), deterministic triggers
(CPM threshold, ambiguous intent), LLM-based trigger classification
(hostile tone, legal language, unusual deliverables), and full evaluation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from negotiation.slack.triggers import (
    EscalationTriggersConfig,
    TriggerClassification,
    TriggerConfig,
    TriggerResult,
    TriggerType,
    classify_triggers,
    evaluate_triggers,
    load_triggers_config,
)


# ---------------------------------------------------------------------------
# TriggerType enum tests
# ---------------------------------------------------------------------------

class TestTriggerType:
    """Test TriggerType StrEnum values."""

    def test_has_five_members(self) -> None:
        assert len(TriggerType) == 5

    def test_cpm_over_threshold_value(self) -> None:
        assert TriggerType.CPM_OVER_THRESHOLD == "cpm_over_threshold"

    def test_ambiguous_intent_value(self) -> None:
        assert TriggerType.AMBIGUOUS_INTENT == "ambiguous_intent"

    def test_hostile_tone_value(self) -> None:
        assert TriggerType.HOSTILE_TONE == "hostile_tone"

    def test_legal_language_value(self) -> None:
        assert TriggerType.LEGAL_LANGUAGE == "legal_language"

    def test_unusual_deliverables_value(self) -> None:
        assert TriggerType.UNUSUAL_DELIVERABLES == "unusual_deliverables"


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------

class TestLoadTriggersConfig:
    """Test YAML config loading with Pydantic validation."""

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        """Missing YAML file falls back to all-defaults."""
        config = load_triggers_config(tmp_path / "nonexistent.yaml")
        assert config.cpm_over_threshold.enabled is True
        assert config.cpm_over_threshold.cpm_threshold == 30.0
        assert config.ambiguous_intent.enabled is True
        assert config.hostile_tone.enabled is True
        assert config.legal_language.enabled is True
        assert config.unusual_deliverables.enabled is True

    def test_empty_file_returns_defaults(self, tmp_path: Path) -> None:
        """Empty YAML file falls back to all-defaults."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        config = load_triggers_config(empty_file)
        assert config.cpm_over_threshold.enabled is True
        assert config.cpm_over_threshold.cpm_threshold == 30.0

    def test_partial_config_fills_defaults(self, tmp_path: Path) -> None:
        """Partial YAML fills missing triggers with defaults."""
        partial = tmp_path / "partial.yaml"
        partial.write_text("cpm_over_threshold:\n  enabled: false\n  cpm_threshold: 50.0\n")
        config = load_triggers_config(partial)
        assert config.cpm_over_threshold.enabled is False
        assert config.cpm_over_threshold.cpm_threshold == 50.0
        # Other triggers should still be defaults (enabled)
        assert config.hostile_tone.enabled is True

    def test_full_config_loads_all_fields(self, tmp_path: Path) -> None:
        """Full YAML config loads correctly."""
        full = tmp_path / "full.yaml"
        full.write_text(
            "cpm_over_threshold:\n"
            "  enabled: true\n"
            "  cpm_threshold: 25.0\n"
            "ambiguous_intent:\n"
            "  enabled: false\n"
            "hostile_tone:\n"
            "  enabled: true\n"
            "  always_trigger_keywords:\n"
            "    - lawsuit\n"
            "    - lawyer\n"
            "legal_language:\n"
            "  enabled: true\n"
            "unusual_deliverables:\n"
            "  enabled: false\n"
        )
        config = load_triggers_config(full)
        assert config.cpm_over_threshold.cpm_threshold == 25.0
        assert config.ambiguous_intent.enabled is False
        assert config.hostile_tone.always_trigger_keywords == ["lawsuit", "lawyer"]
        assert config.unusual_deliverables.enabled is False

    def test_invalid_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """Invalid YAML falls back to all-defaults (log warning, don't crash)."""
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{{{invalid yaml content")
        config = load_triggers_config(bad)
        assert config.cpm_over_threshold.enabled is True
        assert config.cpm_over_threshold.cpm_threshold == 30.0

    def test_default_cpm_threshold_is_30(self) -> None:
        """Default CPM threshold is 30.0 per RESEARCH.md."""
        config = EscalationTriggersConfig()
        assert config.cpm_over_threshold.cpm_threshold == 30.0

    def test_all_triggers_enabled_by_default(self) -> None:
        """All 5 triggers are enabled by default."""
        config = EscalationTriggersConfig()
        assert config.cpm_over_threshold.enabled is True
        assert config.ambiguous_intent.enabled is True
        assert config.hostile_tone.enabled is True
        assert config.legal_language.enabled is True
        assert config.unusual_deliverables.enabled is True


# ---------------------------------------------------------------------------
# Deterministic trigger tests
# ---------------------------------------------------------------------------

class TestCpmOverThresholdTrigger:
    """Test the CPM-over-threshold deterministic trigger."""

    def test_fires_when_cpm_exceeds_threshold(self) -> None:
        """CPM 35.0 exceeds threshold 30.0 -> fires."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Thanks for the offer",
            proposed_cpm=35.0,
            intent_confidence=0.9,
            config=config,
            client=None,  # No LLM triggers for this test
        )
        cpm_results = [r for r in results if r.trigger_type == TriggerType.CPM_OVER_THRESHOLD]
        assert len(cpm_results) == 1
        assert cpm_results[0].fired is True
        assert "35.00" in cpm_results[0].reason
        assert "30.00" in cpm_results[0].reason

    def test_does_not_fire_when_cpm_below_threshold(self) -> None:
        """CPM 25.0 below threshold 30.0 -> does not fire."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Thanks for the offer",
            proposed_cpm=25.0,
            intent_confidence=0.9,
            config=config,
            client=None,
        )
        cpm_results = [r for r in results if r.trigger_type == TriggerType.CPM_OVER_THRESHOLD]
        assert len(cpm_results) == 0

    def test_does_not_fire_at_exact_threshold(self) -> None:
        """CPM exactly at threshold 30.0 -> does NOT fire (exclusive comparison)."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Thanks for the offer",
            proposed_cpm=30.0,
            intent_confidence=0.9,
            config=config,
            client=None,
        )
        cpm_results = [r for r in results if r.trigger_type == TriggerType.CPM_OVER_THRESHOLD]
        assert len(cpm_results) == 0

    def test_disabled_does_not_fire(self) -> None:
        """Disabled CPM trigger does not fire even with high CPM."""
        config = EscalationTriggersConfig(
            cpm_over_threshold=TriggerConfig(enabled=False, cpm_threshold=30.0)
        )
        results = evaluate_triggers(
            email_body="Thanks for the offer",
            proposed_cpm=50.0,
            intent_confidence=0.9,
            config=config,
            client=None,
        )
        cpm_results = [r for r in results if r.trigger_type == TriggerType.CPM_OVER_THRESHOLD]
        assert len(cpm_results) == 0


class TestAmbiguousIntentTrigger:
    """Test the ambiguous-intent deterministic trigger."""

    def test_fires_when_confidence_below_threshold(self) -> None:
        """Confidence 0.5 below default 0.70 -> fires."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Something something",
            proposed_cpm=20.0,
            intent_confidence=0.5,
            config=config,
            client=None,
        )
        intent_results = [r for r in results if r.trigger_type == TriggerType.AMBIGUOUS_INTENT]
        assert len(intent_results) == 1
        assert intent_results[0].fired is True
        assert "0.50" in intent_results[0].reason

    def test_does_not_fire_when_confidence_high(self) -> None:
        """Confidence 0.9 above threshold -> does not fire."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Something something",
            proposed_cpm=20.0,
            intent_confidence=0.9,
            config=config,
            client=None,
        )
        intent_results = [r for r in results if r.trigger_type == TriggerType.AMBIGUOUS_INTENT]
        assert len(intent_results) == 0

    def test_does_not_fire_at_exact_threshold(self) -> None:
        """Confidence exactly 0.70 -> does NOT fire (matches 03-02 behavior)."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Something something",
            proposed_cpm=20.0,
            intent_confidence=0.70,
            config=config,
            client=None,
        )
        intent_results = [r for r in results if r.trigger_type == TriggerType.AMBIGUOUS_INTENT]
        assert len(intent_results) == 0

    def test_disabled_does_not_fire(self) -> None:
        """Disabled ambiguous intent trigger does not fire."""
        config = EscalationTriggersConfig(
            ambiguous_intent=TriggerConfig(enabled=False)
        )
        results = evaluate_triggers(
            email_body="Something something",
            proposed_cpm=20.0,
            intent_confidence=0.3,
            config=config,
            client=None,
        )
        intent_results = [r for r in results if r.trigger_type == TriggerType.AMBIGUOUS_INTENT]
        assert len(intent_results) == 0


# ---------------------------------------------------------------------------
# LLM classification tests (mocked)
# ---------------------------------------------------------------------------

class TestClassifyTriggers:
    """Test LLM-based trigger classification (mocked Anthropic client)."""

    def _make_mock_client(self, classification: TriggerClassification) -> MagicMock:
        """Create a mock Anthropic client returning the given classification."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_output = classification
        mock_client.messages.parse.return_value = mock_response
        return mock_client

    def test_hostile_tone_detected(self) -> None:
        """Hostile email returns hostile_tone_detected=True with evidence."""
        classification = TriggerClassification(
            hostile_tone_detected=True,
            hostile_evidence="I'll make sure no one works with you again",
            legal_language_detected=False,
            legal_evidence="",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        result = classify_triggers("I'll make sure no one works with you again", mock_client)
        assert result.hostile_tone_detected is True
        assert "no one works with you" in result.hostile_evidence

    def test_legal_language_detected(self) -> None:
        """Legal email returns legal_language_detected=True with evidence."""
        classification = TriggerClassification(
            hostile_tone_detected=False,
            hostile_evidence="",
            legal_language_detected=True,
            legal_evidence="my lawyer will review the contract terms",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        result = classify_triggers("my lawyer will review the contract terms", mock_client)
        assert result.legal_language_detected is True
        assert "lawyer" in result.legal_evidence

    def test_unusual_deliverables_detected(self) -> None:
        """Unusual deliverable request returns unusual_deliverables_detected=True."""
        classification = TriggerClassification(
            hostile_tone_detected=False,
            hostile_evidence="",
            legal_language_detected=False,
            legal_evidence="",
            unusual_deliverables_detected=True,
            unusual_evidence="I'd also like you to fly me out for an event appearance",
        )
        mock_client = self._make_mock_client(classification)
        result = classify_triggers(
            "I'd also like you to fly me out for an event appearance", mock_client
        )
        assert result.unusual_deliverables_detected is True
        assert "event appearance" in result.unusual_evidence

    def test_benign_email_no_triggers(self) -> None:
        """Normal email returns all triggers False."""
        classification = TriggerClassification(
            hostile_tone_detected=False,
            hostile_evidence="",
            legal_language_detected=False,
            legal_evidence="",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        result = classify_triggers("Sounds good, I accept the rate!", mock_client)
        assert result.hostile_tone_detected is False
        assert result.legal_language_detected is False
        assert result.unusual_deliverables_detected is False

    def test_classify_calls_anthropic_messages_parse(self) -> None:
        """classify_triggers calls client.messages.parse with correct args."""
        classification = TriggerClassification(
            hostile_tone_detected=False,
            hostile_evidence="",
            legal_language_detected=False,
            legal_evidence="",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        classify_triggers("Test email", mock_client)
        mock_client.messages.parse.assert_called_once()
        call_kwargs = mock_client.messages.parse.call_args[1]
        assert call_kwargs["max_tokens"] == 512
        assert call_kwargs["output_format"] is TriggerClassification

    def test_none_parsed_output_raises_runtime_error(self) -> None:
        """RuntimeError raised if parsed_output is None."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_output = None
        mock_client.messages.parse.return_value = mock_response
        with pytest.raises(RuntimeError, match="Trigger classification returned None"):
            classify_triggers("Test email", mock_client)


# ---------------------------------------------------------------------------
# Full evaluation tests
# ---------------------------------------------------------------------------

class TestEvaluateTriggers:
    """Test the full evaluate_triggers pipeline."""

    def _make_mock_client(self, classification: TriggerClassification) -> MagicMock:
        """Create a mock Anthropic client returning the given classification."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed_output = classification
        mock_client.messages.parse.return_value = mock_response
        return mock_client

    def test_benign_email_no_triggers(self) -> None:
        """Normal email, normal CPM, high confidence -> empty list."""
        classification = TriggerClassification(
            hostile_tone_detected=False,
            hostile_evidence="",
            legal_language_detected=False,
            legal_evidence="",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        results = evaluate_triggers(
            email_body="Sounds good, let's do it!",
            proposed_cpm=20.0,
            intent_confidence=0.95,
            config=EscalationTriggersConfig(),
            client=mock_client,
        )
        assert results == []

    def test_multiple_triggers_fire(self) -> None:
        """Multiple triggers can fire simultaneously."""
        classification = TriggerClassification(
            hostile_tone_detected=True,
            hostile_evidence="You'll regret this",
            legal_language_detected=True,
            legal_evidence="my lawyer will be in touch",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        results = evaluate_triggers(
            email_body="You'll regret this. My lawyer will be in touch.",
            proposed_cpm=35.0,
            intent_confidence=0.5,
            config=EscalationTriggersConfig(),
            client=mock_client,
        )
        trigger_types = {r.trigger_type for r in results}
        assert TriggerType.CPM_OVER_THRESHOLD in trigger_types
        assert TriggerType.AMBIGUOUS_INTENT in trigger_types
        assert TriggerType.HOSTILE_TONE in trigger_types
        assert TriggerType.LEGAL_LANGUAGE in trigger_types

    def test_skips_llm_call_when_all_llm_triggers_disabled(self) -> None:
        """No LLM API call when all 3 LLM triggers are disabled."""
        config = EscalationTriggersConfig(
            hostile_tone=TriggerConfig(enabled=False),
            legal_language=TriggerConfig(enabled=False),
            unusual_deliverables=TriggerConfig(enabled=False),
        )
        mock_client = MagicMock()
        results = evaluate_triggers(
            email_body="Test email",
            proposed_cpm=20.0,
            intent_confidence=0.9,
            config=config,
            client=mock_client,
        )
        # Should NOT call the LLM
        mock_client.messages.parse.assert_not_called()
        assert results == []

    def test_returns_only_fired_triggers(self) -> None:
        """Only fired triggers appear in results list."""
        classification = TriggerClassification(
            hostile_tone_detected=True,
            hostile_evidence="threatening language here",
            legal_language_detected=False,
            legal_evidence="",
            unusual_deliverables_detected=False,
            unusual_evidence="",
        )
        mock_client = self._make_mock_client(classification)
        results = evaluate_triggers(
            email_body="Some threatening email",
            proposed_cpm=20.0,
            intent_confidence=0.9,
            config=EscalationTriggersConfig(),
            client=mock_client,
        )
        assert len(results) == 1
        assert results[0].trigger_type == TriggerType.HOSTILE_TONE
        assert results[0].fired is True
        assert "threatening language here" in results[0].evidence

    def test_client_none_skips_llm_triggers(self) -> None:
        """When client is None, LLM triggers are skipped gracefully."""
        config = EscalationTriggersConfig()
        results = evaluate_triggers(
            email_body="Test email with hostile and legal language",
            proposed_cpm=35.0,
            intent_confidence=0.5,
            config=config,
            client=None,
        )
        # Only deterministic triggers should fire
        trigger_types = {r.trigger_type for r in results}
        assert TriggerType.CPM_OVER_THRESHOLD in trigger_types
        assert TriggerType.AMBIGUOUS_INTENT in trigger_types
        # LLM triggers should NOT be in results
        assert TriggerType.HOSTILE_TONE not in trigger_types
        assert TriggerType.LEGAL_LANGUAGE not in trigger_types
        assert TriggerType.UNUSUAL_DELIVERABLES not in trigger_types


# ---------------------------------------------------------------------------
# TriggerResult model tests
# ---------------------------------------------------------------------------

class TestTriggerResult:
    """Test TriggerResult Pydantic model."""

    def test_create_with_all_fields(self) -> None:
        result = TriggerResult(
            trigger_type=TriggerType.CPM_OVER_THRESHOLD,
            fired=True,
            reason="CPM $35.00 exceeds threshold $30.00",
            evidence="",
        )
        assert result.trigger_type == TriggerType.CPM_OVER_THRESHOLD
        assert result.fired is True
        assert "35.00" in result.reason

    def test_defaults_for_reason_and_evidence(self) -> None:
        result = TriggerResult(
            trigger_type=TriggerType.HOSTILE_TONE,
            fired=False,
        )
        assert result.reason == ""
        assert result.evidence == ""


# ---------------------------------------------------------------------------
# TriggerClassification model tests
# ---------------------------------------------------------------------------

class TestTriggerClassification:
    """Test TriggerClassification Pydantic model."""

    def test_all_false_by_default_evidence(self) -> None:
        """Evidence fields default to empty string."""
        tc = TriggerClassification(
            hostile_tone_detected=False,
            legal_language_detected=False,
            unusual_deliverables_detected=False,
        )
        assert tc.hostile_evidence == ""
        assert tc.legal_evidence == ""
        assert tc.unusual_evidence == ""
