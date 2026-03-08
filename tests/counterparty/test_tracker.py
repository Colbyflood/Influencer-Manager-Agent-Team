"""Tests for per-thread contact tracking across multi-person threads."""

from __future__ import annotations

from negotiation.counterparty.models import CounterpartyProfile, CounterpartyType, DetectionSignal
from negotiation.counterparty.tracker import ThreadContact, ThreadContactTracker


def _make_profile(
    ctype: CounterpartyType = CounterpartyType.DIRECT_INFLUENCER,
    confidence: float = 0.8,
    agency_name: str | None = None,
    contact_name: str | None = None,
    contact_title: str | None = None,
) -> CounterpartyProfile:
    """Create a CounterpartyProfile for testing."""
    return CounterpartyProfile(
        counterparty_type=ctype,
        confidence=confidence,
        signals=[],
        agency_name=agency_name,
        contact_name=contact_name,
        contact_title=contact_title,
    )


class TestThreadContactTracker:
    """Tests for ThreadContactTracker class."""

    def test_single_contact_is_primary(self) -> None:
        """First contact added to a thread is marked as primary."""
        tracker = ThreadContactTracker()
        profile = _make_profile()
        contact = tracker.update("thread_1", "creator@gmail.com", profile)

        assert contact.is_primary is True
        assert contact.email == "creator@gmail.com"
        assert contact.counterparty_type == CounterpartyType.DIRECT_INFLUENCER

    def test_second_contact_is_not_primary(self) -> None:
        """Second contact added is not primary; original remains primary."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator@gmail.com", _make_profile())
        contact2 = tracker.update(
            "thread_1",
            "assistant@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER),
        )

        assert contact2.is_primary is False

        # Original still primary
        contacts = tracker.get_contacts("thread_1")
        primary = [c for c in contacts if c.is_primary]
        assert len(primary) == 1
        assert primary[0].email == "creator@gmail.com"

    def test_manager_upgrades_thread_type_from_direct_influencer(self) -> None:
        """Detecting a talent_manager upgrades thread type from direct_influencer."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator@gmail.com", _make_profile())
        assert tracker.get_primary_type("thread_1") == CounterpartyType.DIRECT_INFLUENCER

        tracker.update(
            "thread_1",
            "mgr@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER),
        )
        assert tracker.get_primary_type("thread_1") == CounterpartyType.TALENT_MANAGER

    def test_agency_name_persisted_from_profile(self) -> None:
        """Agency name from profile is stored on the thread registry."""
        tracker = ThreadContactTracker()
        tracker.update(
            "thread_1",
            "mgr@unitedtalent.com",
            _make_profile(
                CounterpartyType.TALENT_MANAGER,
                agency_name="United Talent Agency",
            ),
        )
        assert tracker.get_agency_name("thread_1") == "United Talent Agency"

    def test_get_contacts_returns_primary_first(self) -> None:
        """get_contacts returns primary contact before non-primary."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator@gmail.com", _make_profile())
        tracker.update(
            "thread_1",
            "assistant@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER),
        )
        tracker.update(
            "thread_1",
            "another@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER),
        )

        contacts = tracker.get_contacts("thread_1")
        assert len(contacts) == 3
        assert contacts[0].is_primary is True
        assert contacts[0].email == "creator@gmail.com"

    def test_has_multiple_contacts_after_second(self) -> None:
        """has_multiple_contacts returns True after second distinct email."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator@gmail.com", _make_profile())
        assert tracker.has_multiple_contacts("thread_1") is False

        tracker.update(
            "thread_1",
            "assistant@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER),
        )
        assert tracker.has_multiple_contacts("thread_1") is True

    def test_unknown_thread_returns_defaults(self) -> None:
        """Unknown thread returns empty contacts, default type, no agency."""
        tracker = ThreadContactTracker()
        assert tracker.get_contacts("unknown") == []
        assert tracker.get_primary_type("unknown") == CounterpartyType.DIRECT_INFLUENCER
        assert tracker.get_agency_name("unknown") is None
        assert tracker.has_multiple_contacts("unknown") is False

    def test_same_email_does_not_duplicate(self) -> None:
        """Repeated updates with same email do not create duplicate contacts."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator@gmail.com", _make_profile())
        tracker.update("thread_1", "creator@gmail.com", _make_profile())

        contacts = tracker.get_contacts("thread_1")
        assert len(contacts) == 1

    def test_email_key_is_case_insensitive(self) -> None:
        """Same email with different casing treated as same contact."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "Creator@Gmail.COM", _make_profile())
        tracker.update("thread_1", "creator@gmail.com", _make_profile())

        contacts = tracker.get_contacts("thread_1")
        assert len(contacts) == 1

    def test_contact_name_and_title_stored(self) -> None:
        """Contact name and title from profile are stored on the contact."""
        tracker = ThreadContactTracker()
        profile = _make_profile(
            contact_name="Jane Manager",
            contact_title="Talent Manager",
        )
        contact = tracker.update("thread_1", "jane@agency.com", profile)

        assert contact.name == "Jane Manager"
        assert contact.title == "Talent Manager"

    def test_first_seen_at_is_iso_timestamp(self) -> None:
        """first_seen_at is a valid ISO 8601 timestamp string."""
        tracker = ThreadContactTracker()
        contact = tracker.update("thread_1", "creator@gmail.com", _make_profile())

        # Should parse without error
        assert "T" in contact.first_seen_at
        assert "+" in contact.first_seen_at or "Z" in contact.first_seen_at

    def test_get_known_emails(self) -> None:
        """get_known_emails returns all email addresses seen on a thread."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator@gmail.com", _make_profile())
        tracker.update(
            "thread_1",
            "mgr@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER),
        )

        emails = tracker.get_known_emails("thread_1")
        assert emails == {"creator@gmail.com", "mgr@agency.com"}

    def test_get_known_emails_unknown_thread(self) -> None:
        """get_known_emails returns empty set for unknown thread."""
        tracker = ThreadContactTracker()
        assert tracker.get_known_emails("unknown") == set()

    def test_multiple_threads_independent(self) -> None:
        """Different threads are tracked independently."""
        tracker = ThreadContactTracker()
        tracker.update("thread_1", "creator1@gmail.com", _make_profile())
        tracker.update(
            "thread_2",
            "mgr@agency.com",
            _make_profile(CounterpartyType.TALENT_MANAGER, agency_name="Agency X"),
        )

        assert tracker.get_primary_type("thread_1") == CounterpartyType.DIRECT_INFLUENCER
        assert tracker.get_primary_type("thread_2") == CounterpartyType.TALENT_MANAGER
        assert tracker.get_agency_name("thread_1") is None
        assert tracker.get_agency_name("thread_2") == "Agency X"
