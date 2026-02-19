"""Slack slash command handlers for human takeover management.

Provides ``register_commands`` to register ``/claim`` and ``/resume``
slash commands on a Bolt ``App`` instance.  Command handlers interact
with a :class:`~negotiation.slack.takeover.ThreadStateManager` to
track thread ownership.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from slack_bolt import App

    from negotiation.slack.takeover import ThreadStateManager


def register_commands(app: App, thread_state_manager: ThreadStateManager) -> None:
    """Register ``/claim`` and ``/resume`` slash commands on the Bolt app.

    Args:
        app: The Slack Bolt ``App`` instance.
        thread_state_manager: The thread state manager for claim/resume operations.
    """

    @app.command("/claim")
    def handle_claim(
        ack: Callable[[], None],
        command: dict[str, Any],
        respond: Callable[..., None],
    ) -> None:
        """Handle /claim command -- mark a thread as human-managed."""
        ack()
        identifier = command.get("text", "").strip()
        if not identifier:
            respond("Usage: /claim <influencer_name_or_email>")
            return
        thread_state_manager.claim_thread(identifier, command["user_id"])
        respond(f"Thread claimed for {identifier}. Agent will stop processing this negotiation.")

    @app.command("/resume")
    def handle_resume(
        ack: Callable[[], None],
        command: dict[str, Any],
        respond: Callable[..., None],
    ) -> None:
        """Handle /resume command -- hand a thread back to the agent."""
        ack()
        identifier = command.get("text", "").strip()
        if not identifier:
            respond("Usage: /resume <influencer_name_or_email>")
            return
        thread_state_manager.resume_thread(identifier)
        respond(f"Thread resumed for {identifier}. Agent will handle this negotiation again.")
