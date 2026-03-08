"""Tests for SOW formatter including strikethrough rate formatting.

Verifies that format_rate_adjustment produces correct strikethrough
output and format_sow_block builds properly structured SOW text blocks.
"""

from negotiation.llm.sow_formatter import format_rate_adjustment, format_sow_block


class TestFormatRateAdjustment:
    """Tests for format_rate_adjustment function."""

    def test_format_rate_adjustment_different_rates(self):
        """Strikethrough appears when original and adjusted rates differ."""
        result = format_rate_adjustment("2000", "1500")
        assert "~~$2,000.00~~" in result
        assert "$1,500.00" in result

    def test_format_rate_adjustment_same_rates(self):
        """No strikethrough when rates are the same."""
        result = format_rate_adjustment("1500", "1500")
        assert "~~" not in result
        assert result == "$1,500.00"

    def test_format_rate_adjustment_comma_formatting(self):
        """Thousands get comma separators in formatted rates."""
        result = format_rate_adjustment("10000", "7500")
        assert "$10,000.00" in result
        assert "$7,500.00" in result

    def test_format_rate_adjustment_already_formatted_input(self):
        """Handles input that already has dollar signs or commas."""
        result = format_rate_adjustment("$2,000", "$1,500")
        assert "~~$2,000.00~~" in result
        assert "$1,500.00" in result

    def test_format_rate_adjustment_decimal_input(self):
        """Handles input with decimal cents."""
        result = format_rate_adjustment("2000.00", "1500.50")
        assert "$2,000.00" in result
        assert "$1,500.50" in result


class TestFormatSowBlock:
    """Tests for format_sow_block function."""

    def test_format_sow_block_basic(self):
        """Deliverables, usage rights, and rate all present in output."""
        result = format_sow_block(
            deliverables_summary="2x Instagram Reels, 1x Story",
            usage_rights_summary="12 months paid amplification",
            rate_display="$1,500.00",
            platform="instagram",
        )
        assert "Scope of Work:" in result
        assert "2x Instagram Reels" in result
        assert "1x Story" in result
        assert "Usage Rights: 12 months paid amplification" in result
        assert "Rate: $1,500.00" in result

    def test_format_sow_block_no_usage_rights(self):
        """Defaults to 'per standard terms' when usage_rights_summary is None."""
        result = format_sow_block(
            deliverables_summary="1x TikTok video",
            usage_rights_summary=None,
            rate_display="$800.00",
            platform="tiktok",
        )
        assert "Usage Rights: per standard terms" in result

    def test_format_sow_block_comma_separated_deliverables(self):
        """Parses comma-separated deliverables into individual bullet points."""
        result = format_sow_block(
            deliverables_summary="2x IG Reels, 3x IG Stories, 1x TikTok video",
            usage_rights_summary="6 months",
            rate_display="$2,000.00",
            platform="instagram",
        )
        lines = result.split("\n")
        # First line is "Scope of Work:"
        # Then 3 deliverable bullets + usage rights + rate = 5 bullet lines
        bullet_lines = [line for line in lines if line.startswith("- ")]
        assert len(bullet_lines) == 5  # 3 deliverables + usage rights + rate

    def test_format_sow_block_multiline_deliverables(self):
        """Parses newline-separated deliverables into bullet points."""
        deliverables = "2x Instagram Reels\n1x Story\n1x TikTok video"
        result = format_sow_block(
            deliverables_summary=deliverables,
            usage_rights_summary="3 months",
            rate_display="$1,200.00",
            platform="instagram",
        )
        assert "- 2x Instagram Reels" in result
        assert "- 1x Story" in result
        assert "- 1x TikTok video" in result

    def test_format_sow_block_strikethrough_rate(self):
        """SOW block correctly includes strikethrough rate display."""
        rate_display = format_rate_adjustment("2000", "1500")
        result = format_sow_block(
            deliverables_summary="1x YouTube dedicated video",
            usage_rights_summary="12 months",
            rate_display=rate_display,
            platform="youtube",
        )
        assert "~~$2,000.00~~ $1,500.00" in result
