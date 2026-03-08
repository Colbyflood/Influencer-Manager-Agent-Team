"""Tests for counterparty tone guidance generation.

Verifies that get_tone_guidance returns appropriate communication style
instructions for talent managers vs direct influencers, and defaults
safely when no counterparty type is provided.
"""

from negotiation.counterparty.tone import get_tone_guidance


class TestToneGuidanceTalentManager:
    """Tests for talent manager tone guidance."""

    def test_talent_manager_contains_data_keywords(self):
        """Talent manager guidance includes data-backed language."""
        result = get_tone_guidance("talent_manager")
        assert "data" in result.lower()
        assert "CPM" in result
        assert "professional" in result.lower()

    def test_talent_manager_with_agency_name(self):
        """Talent manager guidance includes agency name when provided."""
        result = get_tone_guidance("talent_manager", "UTA")
        assert "UTA" in result
        assert "talent manager/agency representative from UTA" in result

    def test_talent_manager_without_agency_name(self):
        """Talent manager guidance works without agency name."""
        result = get_tone_guidance("talent_manager")
        assert "talent manager/agency representative." in result
        assert " from " not in result.split("representative")[1].split("\n")[0]

    def test_talent_manager_includes_business_terms(self):
        """Talent manager guidance references business terminology."""
        result = get_tone_guidance("talent_manager")
        assert "ROI" in result
        assert "SOW" in result
        assert "rate card" in result


class TestToneGuidanceDirectInfluencer:
    """Tests for direct influencer tone guidance."""

    def test_direct_influencer_contains_relationship_keywords(self):
        """Direct influencer guidance includes relationship language."""
        result = get_tone_guidance("direct_influencer")
        assert "warm" in result.lower()
        assert "creative" in result.lower()
        assert "partnership" in result.lower()

    def test_direct_influencer_mentions_creator_language(self):
        """Direct influencer guidance uses creator-friendly terms."""
        result = get_tone_guidance("direct_influencer")
        assert "your audience" in result
        assert "collaboration" in result


class TestToneGuidanceDefaults:
    """Tests for default/fallback behavior."""

    def test_empty_string_returns_direct_influencer(self):
        """Empty string counterparty_type defaults to direct influencer."""
        result = get_tone_guidance("")
        assert "warm" in result.lower()
        assert "creative" in result.lower()

    def test_none_returns_direct_influencer(self):
        """None counterparty_type defaults to direct influencer."""
        result = get_tone_guidance(None)
        assert "warm" in result.lower()
        assert "creative" in result.lower()

    def test_no_args_returns_direct_influencer(self):
        """No arguments defaults to direct influencer."""
        result = get_tone_guidance()
        assert "warm" in result.lower()

    def test_unknown_type_returns_direct_influencer(self):
        """Unknown counterparty type defaults to direct influencer."""
        result = get_tone_guidance("unknown_type")
        assert "influencer/creator" in result

    def test_returned_strings_are_nonempty(self):
        """Both guidance types return non-empty strings."""
        assert len(get_tone_guidance("talent_manager")) > 0
        assert len(get_tone_guidance("direct_influencer")) > 0
        assert len(get_tone_guidance(None)) > 0
        assert len(get_tone_guidance("")) > 0
