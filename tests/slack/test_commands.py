"""Tests for Slack slash command handlers (/claim and /resume)."""

from __future__ import annotations

from unittest.mock import MagicMock

from negotiation.slack.commands import register_commands
from negotiation.slack.takeover import ThreadStateManager


def _make_command(text: str, user_id: str = "U12345") -> dict[str, str]:
    """Build a minimal Slack command payload."""
    return {"text": text, "user_id": user_id}


class TestClaimCommand:
    """Tests for the /claim slash command handler."""

    def test_claim_with_valid_identifier_responds_success(self) -> None:
        """Valid /claim responds with success message."""
        app = MagicMock()
        tsm = ThreadStateManager()
        register_commands(app, tsm)

        # Extract the registered handler
        handler = app.command.call_args_list[0][0][0]  # "/claim"
        assert handler == "/claim"
        claim_fn = app.command.return_value.call_args_list[0][0][0]

        ack = MagicMock()
        respond = MagicMock()
        claim_fn(ack=ack, command=_make_command("influencer@example.com"), respond=respond)

        ack.assert_called_once()
        respond.assert_called_once_with(
            "Thread claimed for influencer@example.com. "
            "Agent will stop processing this negotiation."
        )

    def test_claim_with_empty_text_responds_usage(self) -> None:
        """Empty /claim text responds with usage message."""
        app = MagicMock()
        tsm = ThreadStateManager()
        register_commands(app, tsm)

        claim_fn = app.command.return_value.call_args_list[0][0][0]

        ack = MagicMock()
        respond = MagicMock()
        claim_fn(ack=ack, command=_make_command(""), respond=respond)

        ack.assert_called_once()
        respond.assert_called_once_with("Usage: /claim <influencer_name_or_email>")

    def test_claim_calls_thread_state_manager(self) -> None:
        """/claim calls claim_thread with correct args."""
        app = MagicMock()
        tsm = ThreadStateManager()
        register_commands(app, tsm)

        claim_fn = app.command.return_value.call_args_list[0][0][0]

        ack = MagicMock()
        respond = MagicMock()
        claim_fn(
            ack=ack,
            command=_make_command("influencer@example.com", user_id="U99999"),
            respond=respond,
        )

        assert tsm.is_human_managed("influencer@example.com") is True
        assert tsm.get_claimed_by("influencer@example.com") == "U99999"


class TestResumeCommand:
    """Tests for the /resume slash command handler."""

    def test_resume_with_valid_identifier_responds_success(self) -> None:
        """Valid /resume responds with success message."""
        app = MagicMock()
        tsm = ThreadStateManager()
        register_commands(app, tsm)

        # /resume is the second registered command
        resume_fn = app.command.return_value.call_args_list[1][0][0]

        ack = MagicMock()
        respond = MagicMock()
        resume_fn(ack=ack, command=_make_command("influencer@example.com"), respond=respond)

        ack.assert_called_once()
        respond.assert_called_once_with(
            "Thread resumed for influencer@example.com. Agent will handle this negotiation again."
        )

    def test_resume_with_empty_text_responds_usage(self) -> None:
        """Empty /resume text responds with usage message."""
        app = MagicMock()
        tsm = ThreadStateManager()
        register_commands(app, tsm)

        resume_fn = app.command.return_value.call_args_list[1][0][0]

        ack = MagicMock()
        respond = MagicMock()
        resume_fn(ack=ack, command=_make_command(""), respond=respond)

        ack.assert_called_once()
        respond.assert_called_once_with("Usage: /resume <influencer_name_or_email>")

    def test_resume_calls_thread_state_manager(self) -> None:
        """/resume calls resume_thread correctly."""
        app = MagicMock()
        tsm = ThreadStateManager()
        # Pre-claim a thread
        tsm.claim_thread("influencer@example.com", "U12345")
        register_commands(app, tsm)

        resume_fn = app.command.return_value.call_args_list[1][0][0]

        ack = MagicMock()
        respond = MagicMock()
        resume_fn(ack=ack, command=_make_command("influencer@example.com"), respond=respond)

        assert tsm.is_human_managed("influencer@example.com") is False
