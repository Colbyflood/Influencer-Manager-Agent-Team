"""Tests for counterparty detection models."""

from negotiation.counterparty.models import (
    CounterpartyProfile,
    CounterpartyType,
    DetectionSignal,
)


class TestCounterpartyType:
    def test_enum_values(self):
        assert CounterpartyType.DIRECT_INFLUENCER == "direct_influencer"
        assert CounterpartyType.TALENT_MANAGER == "talent_manager"

    def test_string_comparison(self):
        assert CounterpartyType.DIRECT_INFLUENCER == "direct_influencer"
        assert CounterpartyType.TALENT_MANAGER == "talent_manager"


class TestDetectionSignal:
    def test_creation(self):
        signal = DetectionSignal(
            signal_type="agency_domain",
            value="unitedtalent.com",
            strength=1.0,
            indicates=CounterpartyType.TALENT_MANAGER,
        )
        assert signal.signal_type == "agency_domain"
        assert signal.value == "unitedtalent.com"
        assert signal.strength == 1.0
        assert signal.indicates == CounterpartyType.TALENT_MANAGER

    def test_frozen(self):
        signal = DetectionSignal(
            signal_type="agency_domain",
            value="caa.com",
            strength=1.0,
            indicates=CounterpartyType.TALENT_MANAGER,
        )
        try:
            signal.value = "changed"
            raise AssertionError("Should have raised")
        except Exception:
            pass


class TestCounterpartyProfile:
    def test_creation_minimal(self):
        profile = CounterpartyProfile(
            counterparty_type=CounterpartyType.DIRECT_INFLUENCER,
            confidence=0.5,
            signals=[],
        )
        assert profile.counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        assert profile.confidence == 0.5
        assert profile.signals == []
        assert profile.agency_name is None
        assert profile.contact_name is None
        assert profile.contact_title is None

    def test_creation_with_metadata(self):
        signal = DetectionSignal(
            signal_type="agency_domain",
            value="unitedtalent.com",
            strength=1.0,
            indicates=CounterpartyType.TALENT_MANAGER,
        )
        profile = CounterpartyProfile(
            counterparty_type=CounterpartyType.TALENT_MANAGER,
            confidence=0.9,
            signals=[signal],
            agency_name="United Talent Agency",
            contact_name="Sarah",
            contact_title="Talent Manager",
        )
        assert profile.agency_name == "United Talent Agency"
        assert profile.contact_name == "Sarah"
        assert profile.contact_title == "Talent Manager"

    def test_frozen(self):
        profile = CounterpartyProfile(
            counterparty_type=CounterpartyType.DIRECT_INFLUENCER,
            confidence=0.5,
            signals=[],
        )
        try:
            profile.confidence = 0.9
            raise AssertionError("Should have raised")
        except Exception:
            pass
