"""Tests for deterministic email validation gate.

These tests are entirely deterministic -- no mocks needed since
validate_composed_email uses only regex and string matching (no LLM calls).
"""

from decimal import Decimal

from negotiation.llm.models import ValidationResult
from negotiation.llm.validation import validate_composed_email


class TestValidateComposedEmail:
    """Tests for validate_composed_email function."""

    def test_clean_email_passes(self):
        """Email with correct rate and deliverables passes validation."""
        email = (
            "Hi Sarah,\n\n"
            "Thank you for your interest in this collaboration. "
            "We'd love to offer you $1,500.00 for this campaign.\n\n"
            "The deliverables would include 2 Instagram Reels and 1 Story.\n\n"
            "Looking forward to working together!\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel", "story"],
            influencer_name="Sarah",
        )
        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert len([f for f in result.failures if f.severity == "error"]) == 0

    def test_wrong_monetary_value_fails(self):
        """Email with a wrong dollar amount triggers monetary_value failure."""
        email = (
            "Hi Sarah,\n\n"
            "We are pleased to offer you $1,200.00 for this partnership.\n\n"
            "The deliverables include 2 Instagram Reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1250.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "monetary_value" in error_checks

    def test_multiple_dollar_amounts_one_wrong(self):
        """Email with correct rate and extra unrelated dollar amount fails."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign. "
            "Our typical budget for similar work is $2,000.00.\n\n"
            "The deliverables include Instagram Reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "monetary_value" in error_checks

    def test_hallucinated_exclusivity(self):
        """Email mentioning 'exclusivity' triggers hallucinated_commitment failure."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign with exclusivity "
            "to our brand.\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "hallucinated_commitment" in error_checks

    def test_hallucinated_usage_rights(self):
        """Email mentioning 'usage rights' triggers hallucinated_commitment failure."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign. "
            "This includes usage rights for all content.\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "hallucinated_commitment" in error_checks

    def test_hallucinated_future_deals(self):
        """Email promising 'future deals' triggers hallucinated_commitment failure."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign. "
            "We can discuss future partnership opportunities as well.\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "hallucinated_commitment" in error_checks

    def test_hallucinated_guarantee(self):
        """Email with 'guarantee' triggers hallucinated_commitment failure."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign. "
            "We guarantee a high level of engagement.\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "hallucinated_commitment" in error_checks

    def test_missing_deliverable_is_warning(self):
        """Missing expected deliverable produces warning, not error."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign.\n\n"
            "The deliverables include Instagram Reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel", "story"],
            influencer_name="Sarah",
        )
        # Missing deliverable is warning not error, so passed is True
        assert result.passed is True
        warning_checks = [f.check for f in result.failures if f.severity == "warning"]
        assert "deliverable_coverage" in warning_checks

    def test_forbidden_phrases(self):
        """Email containing a forbidden phrase triggers off_brand_language failure."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign. "
            "This is a once-in-a-lifetime opportunity!\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
            forbidden_phrases=["once-in-a-lifetime", "limited time"],
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "off_brand_language" in error_checks

    def test_too_short_email(self):
        """Email shorter than 50 characters fails validation."""
        email = "Hi Sarah, here is your offer."
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        assert "too_short" in error_checks

    def test_only_warnings_passes(self):
        """Email with warnings but no errors still passes validation."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign.\n\n"
            "We're excited to work with you on this project "
            "and believe it will be a great fit for both parties.\n\n"
            "Best regards"
        )
        # Missing all deliverables = warnings, but no errors
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel", "story", "tiktok_video"],
            influencer_name="Sarah",
        )
        assert result.passed is True
        assert len(result.failures) > 0  # Has warnings
        assert all(f.severity == "warning" for f in result.failures)

    def test_multiple_failures_collected(self):
        """Multiple validation failures are all collected in failures list."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,200.00 for this exclusive campaign. "
            "We guarantee amazing results!\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is False
        error_checks = [f.check for f in result.failures if f.severity == "error"]
        # Should have monetary_value and hallucinated_commitment errors at minimum
        assert len(error_checks) >= 2

    def test_rate_with_comma_formatting(self):
        """Expected rate with comma formatting ($1,250.00) matches correctly."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,250.00 for this campaign.\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1250.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.passed is True

    def test_email_body_included_in_result(self):
        """ValidationResult includes the email body that was validated."""
        email = (
            "Hi Sarah,\n\n"
            "We'd like to offer $1,500.00 for this campaign.\n\n"
            "The deliverables include reels.\n\n"
            "Best regards"
        )
        result = validate_composed_email(
            email_body=email,
            expected_rate=Decimal("1500.00"),
            expected_deliverables=["instagram_reel"],
            influencer_name="Sarah",
        )
        assert result.email_body == email
