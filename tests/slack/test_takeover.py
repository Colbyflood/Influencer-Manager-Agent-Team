"""Tests for human takeover detection and thread state management."""

from __future__ import annotations

from unittest.mock import MagicMock

from negotiation.slack.takeover import ThreadStateManager, detect_human_reply

# ---------------------------------------------------------------------------
# Helper: build a mock Gmail service with thread messages
# ---------------------------------------------------------------------------


def _mock_service_with_messages(from_headers: list[str]) -> MagicMock:
    """Create a mock Gmail service returning a thread with the given From headers."""
    messages = []
    for from_value in from_headers:
        messages.append(
            {
                "payload": {
                    "headers": [{"name": "From", "value": from_value}],
                },
            }
        )

    thread_response = {"messages": messages}

    service = MagicMock()
    (
        service.users()
        .threads()
        .get(userId="me", id="thread_1", format="metadata", metadataHeaders=["From"])
        .execute.return_value
    ) = thread_response

    return service


# ---------------------------------------------------------------------------
# detect_human_reply tests
# ---------------------------------------------------------------------------


class TestDetectHumanReply:
    """Tests for detect_human_reply function."""

    def test_returns_false_when_only_agent_and_influencer(self) -> None:
        """Only agent and influencer emails -- no human reply detected."""
        service = _mock_service_with_messages(["agent@company.com", "influencer@gmail.com"])
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is False

    def test_returns_true_when_third_party_email_present(self) -> None:
        """A third-party email means a human replied."""
        service = _mock_service_with_messages(
            ["agent@company.com", "influencer@gmail.com", "manager@company.com"]
        )
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is True

    def test_handles_name_email_format(self) -> None:
        """From header with 'Name <email>' format is correctly parsed."""
        service = _mock_service_with_messages(
            [
                "Agent Bot <agent@company.com>",
                "Influencer Name <influencer@gmail.com>",
            ]
        )
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is False

    def test_handles_name_email_format_with_third_party(self) -> None:
        """Name <email> format with a third-party triggers detection."""
        service = _mock_service_with_messages(
            [
                "Agent Bot <agent@company.com>",
                "Manager Person <manager@company.com>",
            ]
        )
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is True

    def test_handles_plain_email_format(self) -> None:
        """Plain email format (no display name) works correctly."""
        service = _mock_service_with_messages(["agent@company.com"])
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is False

    def test_is_case_insensitive(self) -> None:
        """Email comparison is case-insensitive."""
        service = _mock_service_with_messages(["Agent@Company.COM", "INFLUENCER@gmail.com"])
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is False

    def test_empty_thread_returns_false(self) -> None:
        """Thread with no messages returns False."""
        service = _mock_service_with_messages([])
        result = detect_human_reply(
            service, "thread_1", "agent@company.com", "influencer@gmail.com"
        )
        assert result is False


# ---------------------------------------------------------------------------
# ThreadStateManager tests
# ---------------------------------------------------------------------------


class TestThreadStateManager:
    """Tests for ThreadStateManager class."""

    def test_new_thread_is_agent_managed(self) -> None:
        """Unknown threads are agent-managed by default."""
        mgr = ThreadStateManager()
        assert mgr.is_human_managed("thread_1") is False

    def test_claim_thread_makes_human_managed(self) -> None:
        """Claiming a thread marks it as human-managed."""
        mgr = ThreadStateManager()
        mgr.claim_thread("thread_1", "U12345")
        assert mgr.is_human_managed("thread_1") is True

    def test_resume_thread_makes_agent_managed(self) -> None:
        """Resuming a thread returns it to agent management."""
        mgr = ThreadStateManager()
        mgr.claim_thread("thread_1", "U12345")
        mgr.resume_thread("thread_1")
        assert mgr.is_human_managed("thread_1") is False

    def test_get_claimed_by_returns_user_id(self) -> None:
        """get_claimed_by returns the user who claimed the thread."""
        mgr = ThreadStateManager()
        mgr.claim_thread("thread_1", "U12345")
        assert mgr.get_claimed_by("thread_1") == "U12345"

    def test_get_claimed_by_returns_none_for_unclaimed(self) -> None:
        """get_claimed_by returns None for unknown threads."""
        mgr = ThreadStateManager()
        assert mgr.get_claimed_by("thread_1") is None

    def test_get_claimed_by_returns_none_after_resume(self) -> None:
        """get_claimed_by returns None after resuming."""
        mgr = ThreadStateManager()
        mgr.claim_thread("thread_1", "U12345")
        mgr.resume_thread("thread_1")
        assert mgr.get_claimed_by("thread_1") is None

    def test_multiple_threads_independent(self) -> None:
        """Different threads are tracked independently."""
        mgr = ThreadStateManager()
        mgr.claim_thread("thread_1", "U12345")
        mgr.claim_thread("thread_2", "U67890")
        assert mgr.is_human_managed("thread_1") is True
        assert mgr.is_human_managed("thread_2") is True
        mgr.resume_thread("thread_1")
        assert mgr.is_human_managed("thread_1") is False
        assert mgr.is_human_managed("thread_2") is True
