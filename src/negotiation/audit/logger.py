"""Convenience class for inserting audit trail entries.

Per locked decision: Log everything -- emails, escalations, takeovers, campaign
starts, state transitions, agreement closures, influencer skips, and errors.
Each method creates a properly structured :class:`AuditEntry` and inserts it
via :func:`insert_audit_entry`.
"""

from __future__ import annotations

import sqlite3

from negotiation.audit.models import AuditEntry, EventType
from negotiation.audit.store import insert_audit_entry


class AuditLogger:
    """Typed convenience API for inserting audit entries.

    Wraps :func:`insert_audit_entry` with per-event-type methods that
    enforce correct field usage for each event type.

    Args:
        conn: An open SQLite connection to the audit database.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def log_email_sent(
        self,
        campaign_id: str | None,
        influencer_name: str,
        thread_id: str,
        email_body: str,
        negotiation_state: str,
        rates_used: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> int:
        """Log an outbound email.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer.
            thread_id: Gmail thread ID.
            email_body: Full email body text.
            negotiation_state: Current negotiation state.
            rates_used: Rate information included in the email.
            metadata: Additional key-value metadata.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.EMAIL_SENT,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            thread_id=thread_id,
            direction="sent",
            email_body=email_body,
            negotiation_state=negotiation_state,
            rates_used=rates_used,
            metadata=metadata,
        )
        return insert_audit_entry(self._conn, entry)

    def log_email_received(
        self,
        campaign_id: str | None,
        influencer_name: str,
        thread_id: str,
        email_body: str,
        negotiation_state: str,
        intent_classification: str | None = None,
        rates_used: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> int:
        """Log an inbound email.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer.
            thread_id: Gmail thread ID.
            email_body: Full email body text.
            negotiation_state: Current negotiation state.
            intent_classification: LLM-classified intent of the reply.
            rates_used: Rate information mentioned in the email.
            metadata: Additional key-value metadata.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.EMAIL_RECEIVED,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            thread_id=thread_id,
            direction="received",
            email_body=email_body,
            negotiation_state=negotiation_state,
            intent_classification=intent_classification,
            rates_used=rates_used,
            metadata=metadata,
        )
        return insert_audit_entry(self._conn, entry)

    def log_state_transition(
        self,
        campaign_id: str | None,
        influencer_name: str,
        thread_id: str | None,
        from_state: str,
        to_state: str,
        event: str,
    ) -> int:
        """Log a negotiation state machine transition.

        Stores from_state, to_state, and event in metadata.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer.
            thread_id: Gmail thread ID (if available).
            from_state: State before transition.
            to_state: State after transition.
            event: Event that triggered the transition.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.STATE_TRANSITION,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            thread_id=thread_id,
            metadata={
                "from_state": from_state,
                "to_state": to_state,
                "event": event,
            },
        )
        return insert_audit_entry(self._conn, entry)

    def log_escalation(
        self,
        campaign_id: str | None,
        influencer_name: str,
        thread_id: str | None,
        reason: str,
        negotiation_state: str,
        rates_used: str | None = None,
    ) -> int:
        """Log an escalation to human review.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer.
            thread_id: Gmail thread ID (if available).
            reason: Why escalation was triggered.
            negotiation_state: Current negotiation state.
            rates_used: Rate information at time of escalation.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.ESCALATION,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            thread_id=thread_id,
            negotiation_state=negotiation_state,
            rates_used=rates_used,
            metadata={"reason": reason},
        )
        return insert_audit_entry(self._conn, entry)

    def log_agreement(
        self,
        campaign_id: str | None,
        influencer_name: str,
        thread_id: str | None,
        agreed_rate: str,
        negotiation_state: str,
        metadata: dict[str, str] | None = None,
    ) -> int:
        """Log a successfully agreed deal.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer.
            thread_id: Gmail thread ID (if available).
            agreed_rate: The agreed-upon rate as a string.
            negotiation_state: Current negotiation state.
            metadata: Additional key-value metadata.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.AGREEMENT,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            thread_id=thread_id,
            negotiation_state=negotiation_state,
            rates_used=agreed_rate,
            metadata=metadata,
        )
        return insert_audit_entry(self._conn, entry)

    def log_takeover(
        self,
        campaign_id: str | None,
        influencer_name: str,
        thread_id: str,
        taken_by: str,
    ) -> int:
        """Log a human takeover of a negotiation thread.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer.
            thread_id: Gmail thread ID.
            taken_by: Slack user ID of the person taking over.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.TAKEOVER,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            thread_id=thread_id,
            metadata={"taken_by": taken_by},
        )
        return insert_audit_entry(self._conn, entry)

    def log_campaign_start(
        self,
        campaign_id: str,
        influencer_count: int,
        found_count: int,
        missing_count: int,
    ) -> int:
        """Log the start of a campaign ingestion.

        Args:
            campaign_id: Campaign identifier.
            influencer_count: Total influencers in the campaign.
            found_count: Number of influencers found in database.
            missing_count: Number of influencers not found.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.CAMPAIGN_START,
            campaign_id=campaign_id,
            metadata={
                "influencer_count": str(influencer_count),
                "found_count": str(found_count),
                "missing_count": str(missing_count),
            },
        )
        return insert_audit_entry(self._conn, entry)

    def log_campaign_influencer_skip(
        self,
        campaign_id: str,
        influencer_name: str,
        reason: str,
    ) -> int:
        """Log an influencer being skipped during campaign ingestion.

        Args:
            campaign_id: Campaign identifier.
            influencer_name: Name of the skipped influencer.
            reason: Why the influencer was skipped.

        Returns:
            The row ID of the inserted audit entry.
        """
        entry = AuditEntry(
            event_type=EventType.CAMPAIGN_INFLUENCER_SKIP,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            metadata={"reason": reason},
        )
        return insert_audit_entry(self._conn, entry)

    def log_error(
        self,
        campaign_id: str | None,
        influencer_name: str | None,
        error_message: str,
        context: str | None = None,
    ) -> int:
        """Log an error encountered during processing.

        Args:
            campaign_id: Campaign identifier (if available).
            influencer_name: Name of the influencer (if available).
            error_message: The error message.
            context: Additional context about where the error occurred.

        Returns:
            The row ID of the inserted audit entry.
        """
        meta: dict[str, str] = {"error_message": error_message}
        if context is not None:
            meta["context"] = context

        entry = AuditEntry(
            event_type=EventType.ERROR,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            metadata=meta,
        )
        return insert_audit_entry(self._conn, entry)
