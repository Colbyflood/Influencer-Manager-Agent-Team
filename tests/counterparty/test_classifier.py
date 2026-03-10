"""Tests for counterparty classifier.

Covers: agency domains, personal domains, custom domains, signature keywords,
email structure, ambiguous cases, agency name extraction, and edge cases.
"""

from negotiation.counterparty.classifier import classify_counterparty
from negotiation.counterparty.models import CounterpartyType


class TestAgencyDomainDetection:
    """Classifier detects talent manager from agency email domains."""

    def test_united_talent_domain(self):
        result = classify_counterparty(
            from_email="sarah@unitedtalent.com",
            email_body="Hi, I'm reaching out on behalf of Jake...",
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.9
        assert result.agency_name == "United Talent Agency"

    def test_wmg_agent_domain(self):
        result = classify_counterparty(
            from_email="john@wmgagent.com",
            email_body="Hello, representing our talent roster...",
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.8

    def test_caa_domain(self):
        result = classify_counterparty(
            from_email="agent@caa.com",
            email_body="Regarding your proposal for our client...",
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.8
        assert result.agency_name == "Creative Artists Agency"


class TestPersonalDomainDetection:
    """Classifier detects direct influencer from personal domains."""

    def test_gmail_casual(self):
        result = classify_counterparty(
            from_email="jake.creator@gmail.com",
            email_body="hey! thanks for reaching out, sounds cool!",
        )
        assert result.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert result.confidence >= 0.8

    def test_yahoo_domain(self):
        result = classify_counterparty(
            from_email="influencer123@yahoo.com",
            email_body="I'd love to work together on this!",
        )
        assert result.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert result.confidence >= 0.8

    def test_hotmail_domain(self):
        result = classify_counterparty(
            from_email="creator@hotmail.com",
            email_body="Sure, let me know the details.",
        )
        assert result.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert result.confidence >= 0.8


class TestSignatureKeywordDetection:
    """Classifier detects talent manager from signature keywords."""

    def test_talent_manager_title_in_signature(self):
        body = (
            "We'd love to discuss rates for our talent.\n\n"
            "Best regards,\n"
            "Sarah Johnson\n"
            "Talent Manager\n"
            "Elite Management Group"
        )
        result = classify_counterparty(
            from_email="sarah@elitemanagement.com",
            email_body=body,
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.6

    def test_on_behalf_of_phrase(self):
        body = "I'm writing on behalf of our client regarding the campaign.\n\nThanks,\nMike Davis"
        result = classify_counterparty(
            from_email="mike@customagency.com",
            email_body=body,
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.6

    def test_talent_director_title(self):
        body = "Let's set up a call to discuss.\n\nWarm regards,\nLisa Chen\nTalent Director"
        result = classify_counterparty(
            from_email="manager@company.com",
            email_body=body,
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.8


class TestCustomDomainDetection:
    """Classifier handles custom/unknown domains."""

    def test_custom_domain_neutral_body_defaults_to_influencer(self):
        result = classify_counterparty(
            from_email="info@customdomain.com",
            email_body="Thanks for the information.",
        )
        assert result.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert result.confidence == 0.5

    def test_custom_domain_with_manager_signature(self):
        body = "We're interested in your proposal.\n\nBest regards,\nSarah - Talent Manager"
        result = classify_counterparty(
            from_email="contact@customdomain.com",
            email_body=body,
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.6


class TestEmailStructureDetection:
    """Classifier uses email structure as additional signal."""

    def test_formal_structure_adds_manager_signal(self):
        body = (
            "Dear Team,\n\n"
            "I would like to discuss partnership opportunities.\n\n"
            "Warm regards,\n"
            "Alexandra Smith\n"
            "VP Talent Partnerships"
        )
        result = classify_counterparty(
            from_email="alex@unknowncompany.com",
            email_body=body,
        )
        # VP Talent title + formal structure -> talent_manager
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER

    def test_casual_structure_adds_influencer_signal(self):
        body = "hey! super excited about this collab, let me know!"
        result = classify_counterparty(
            from_email="creator@outlook.com",
            email_body=body,
        )
        assert result.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert result.confidence >= 0.8


class TestConfidenceScoring:
    """Confidence scoring follows specification rules."""

    def test_two_plus_manager_signals_high_confidence(self):
        # Agency domain + "on behalf of" -> 2 signals -> 0.9
        result = classify_counterparty(
            from_email="sarah@unitedtalent.com",
            email_body="Hi, I'm reaching out on behalf of Jake...",
        )
        assert result.confidence >= 0.9

    def test_single_strong_signal_medium_high_confidence(self):
        # Agency domain only, neutral body
        result = classify_counterparty(
            from_email="info@paradigmagency.com",
            email_body="Thanks for your email.",
        )
        assert result.counterparty_type == CounterpartyType.TALENT_MANAGER
        assert result.confidence >= 0.8

    def test_no_signals_default_low_confidence(self):
        result = classify_counterparty(
            from_email="info@unknowndomain.com",
            email_body="Sounds good.",
        )
        assert result.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert result.confidence == 0.5

    def test_signals_list_populated(self):
        result = classify_counterparty(
            from_email="sarah@unitedtalent.com",
            email_body="Hi, on behalf of our client...",
        )
        assert len(result.signals) >= 2
        signal_types = [s.signal_type for s in result.signals]
        assert "agency_domain" in signal_types


class TestAgencyNameExtraction:
    """Agency name extraction from known domains and signatures."""

    def test_known_domain_agency_name(self):
        result = classify_counterparty(
            from_email="agent@icmpartners.com",
            email_body="Looking forward to discussing.",
        )
        assert result.agency_name is not None
        assert "ICM" in result.agency_name

    def test_unknown_domain_no_agency_name(self):
        result = classify_counterparty(
            from_email="person@gmail.com",
            email_body="Hey there!",
        )
        assert result.agency_name is None
