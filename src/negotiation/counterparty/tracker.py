"""Per-thread contact tracking for multi-person negotiation threads.

Maintains a registry of all contacts that have participated in each
negotiation thread, tracking their roles (counterparty type), agency
affiliation, and primary contact status.  Used by the inbound email
pipeline to maintain awareness of all thread participants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from negotiation.counterparty.models import CounterpartyProfile, CounterpartyType


class ThreadContact(BaseModel):
    """A single contact participating in a negotiation thread."""

    model_config = ConfigDict(frozen=True)

    email: str
    name: str | None = None
    counterparty_type: CounterpartyType
    title: str | None = None
    first_seen_at: str  # ISO 8601 timestamp
    is_primary: bool = False


@dataclass
class ThreadContactRegistry:
    """Internal registry tracking all contacts for a single thread."""

    contacts: dict[str, ThreadContact] = field(default_factory=dict)
    agency_name: str | None = None
    primary_counterparty_type: CounterpartyType = CounterpartyType.DIRECT_INFLUENCER


class ThreadContactTracker:
    """Manages per-thread contact lists across all active negotiations.

    Tracks every distinct email sender on each thread, recording their
    counterparty type, agency affiliation, and whether they are the
    primary contact for the thread.
    """

    def __init__(self) -> None:
        self._threads: dict[str, ThreadContactRegistry] = {}

    def update(
        self,
        thread_id: str,
        from_email: str,
        profile: CounterpartyProfile,
    ) -> ThreadContact:
        """Add or update a contact for a thread.

        If this is the first contact on the thread, marks them as primary
        and sets the thread's primary_counterparty_type.  If a talent_manager
        is detected on a thread that was previously direct_influencer,
        upgrades primary_counterparty_type to talent_manager.  Stores
        agency_name if detected.

        Args:
            thread_id: The Gmail thread ID.
            from_email: The sender's email address.
            profile: The classification result from the counterparty classifier.

        Returns:
            The ThreadContact created or updated.
        """
        email_key = from_email.lower()

        if thread_id not in self._threads:
            self._threads[thread_id] = ThreadContactRegistry()

        registry = self._threads[thread_id]
        is_first = len(registry.contacts) == 0
        is_new = email_key not in registry.contacts

        contact = ThreadContact(
            email=from_email,
            name=profile.contact_name,
            counterparty_type=profile.counterparty_type,
            title=profile.contact_title,
            first_seen_at=datetime.now(UTC).isoformat(),
            is_primary=is_first and is_new,
        )

        # Only add new contacts (don't overwrite existing primary status)
        if is_new:
            registry.contacts[email_key] = contact
        else:
            # Update counterparty_type but preserve is_primary and first_seen_at
            existing = registry.contacts[email_key]
            contact = ThreadContact(
                email=from_email,
                name=profile.contact_name or existing.name,
                counterparty_type=profile.counterparty_type,
                title=profile.contact_title or existing.title,
                first_seen_at=existing.first_seen_at,
                is_primary=existing.is_primary,
            )
            registry.contacts[email_key] = contact

        # Set primary type on first contact
        if is_first and is_new:
            registry.primary_counterparty_type = profile.counterparty_type

        # Upgrade thread type if talent_manager detected on direct_influencer thread
        if (
            profile.counterparty_type == CounterpartyType.TALENT_MANAGER
            and registry.primary_counterparty_type == CounterpartyType.DIRECT_INFLUENCER
        ):
            registry.primary_counterparty_type = CounterpartyType.TALENT_MANAGER

        # Store agency name if detected
        if profile.agency_name is not None:
            registry.agency_name = profile.agency_name

        return contact

    def get_contacts(self, thread_id: str) -> list[ThreadContact]:
        """Return all contacts for a thread, primary first.

        Args:
            thread_id: The Gmail thread ID.

        Returns:
            List of ThreadContact, with the primary contact first.
        """
        registry = self._threads.get(thread_id)
        if registry is None:
            return []

        contacts = list(registry.contacts.values())
        # Sort: primary first
        contacts.sort(key=lambda c: (not c.is_primary,))
        return contacts

    def get_primary_type(self, thread_id: str) -> CounterpartyType:
        """Return the thread's primary counterparty type.

        Returns talent_manager if any manager detected, else direct_influencer.

        Args:
            thread_id: The Gmail thread ID.

        Returns:
            The primary CounterpartyType for the thread.
        """
        registry = self._threads.get(thread_id)
        if registry is None:
            return CounterpartyType.DIRECT_INFLUENCER
        return registry.primary_counterparty_type

    def get_agency_name(self, thread_id: str) -> str | None:
        """Return agency name if detected on the thread.

        Args:
            thread_id: The Gmail thread ID.

        Returns:
            The agency name string, or None.
        """
        registry = self._threads.get(thread_id)
        if registry is None:
            return None
        return registry.agency_name

    def has_multiple_contacts(self, thread_id: str) -> bool:
        """Check if more than one distinct email has sent on this thread.

        Args:
            thread_id: The Gmail thread ID.

        Returns:
            True if more than one distinct email address has been seen.
        """
        registry = self._threads.get(thread_id)
        if registry is None:
            return False
        return len(registry.contacts) > 1

    def get_known_emails(self, thread_id: str) -> set[str]:
        """Return the set of known email addresses for a thread.

        Args:
            thread_id: The Gmail thread ID.

        Returns:
            Set of lowercase email addresses seen on this thread.
        """
        registry = self._threads.get(thread_id)
        if registry is None:
            return set()
        return set(registry.contacts.keys())
