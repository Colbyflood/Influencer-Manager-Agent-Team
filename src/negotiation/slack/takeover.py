"""Human takeover detection and thread state management.

Provides ``detect_human_reply`` for identifying when a non-agent,
non-influencer sender has replied in a Gmail thread, and
``ThreadStateManager`` for tracking which threads are human-managed
vs agent-managed.
"""

from __future__ import annotations

import email.utils
from typing import Any


def detect_human_reply(
    service: Any,
    thread_id: str,
    agent_email: str,
    influencer_email: str,
) -> bool:
    """Detect whether a human (non-agent, non-influencer) has replied in a thread.

    Fetches the Gmail thread metadata and inspects the ``From`` header of
    each message.  If any message was sent by someone other than the agent
    or the influencer, returns ``True``.

    Uses :func:`email.utils.parseaddr` (stdlib) for robust email address
    extraction from both ``"Name <email>"`` and plain ``"email"`` formats.

    Args:
        service: An authenticated Gmail API v1 service resource.
        thread_id: The Gmail thread ID to inspect.
        agent_email: The email address used by the agent.
        influencer_email: The influencer's email address.

    Returns:
        ``True`` if a human reply was detected, ``False`` otherwise.
    """
    thread: dict[str, Any] = (
        service.users()
        .threads()
        .get(userId="me", id=thread_id, format="metadata", metadataHeaders=["From"])
        .execute()
    )

    known_senders = {agent_email.lower(), influencer_email.lower()}

    for message in thread.get("messages", []):
        headers = message.get("payload", {}).get("headers", [])
        for header in headers:
            if header.get("name", "").lower() == "from":
                _, addr = email.utils.parseaddr(header["value"])
                if addr and addr.lower() not in known_senders:
                    return True

    return False


class ThreadStateManager:
    """In-memory thread state tracker for human-managed vs agent-managed threads.

    Tracks which negotiation threads have been claimed by a human user
    (via ``/claim``) and which are still under agent control.  Threads
    not explicitly tracked are assumed to be agent-managed.

    This is a v1 in-memory implementation.  A persistent backend can be
    added later without changing the interface.
    """

    def __init__(self) -> None:
        self._state: dict[str, dict[str, str | None]] = {}

    def claim_thread(self, thread_id: str, user_id: str) -> None:
        """Mark a thread as human-managed.

        Args:
            thread_id: The thread identifier (Gmail thread ID or influencer key).
            user_id: The Slack user ID of the person claiming the thread.
        """
        self._state[thread_id] = {"managed_by": "human", "claimed_by": user_id}

    def resume_thread(self, thread_id: str) -> None:
        """Hand a thread back to the agent.

        Args:
            thread_id: The thread identifier to resume.
        """
        self._state[thread_id] = {"managed_by": "agent", "claimed_by": None}

    def is_human_managed(self, thread_id: str) -> bool:
        """Check whether a thread is currently human-managed.

        Args:
            thread_id: The thread identifier to check.

        Returns:
            ``True`` if the thread has been claimed by a human, ``False``
            otherwise (including for unknown threads).
        """
        entry = self._state.get(thread_id)
        if entry is None:
            return False
        return entry["managed_by"] == "human"

    def get_claimed_by(self, thread_id: str) -> str | None:
        """Get the user ID of whoever claimed the thread.

        Args:
            thread_id: The thread identifier to look up.

        Returns:
            The Slack user ID if the thread is claimed, ``None`` otherwise.
        """
        entry = self._state.get(thread_id)
        if entry is None:
            return None
        return entry["claimed_by"]
