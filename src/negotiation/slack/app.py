"""Slack Bolt App initialization and Socket Mode startup.

Provides ``create_slack_app`` for creating a Bolt ``App`` instance
and ``start_slack_app`` for launching it in Socket Mode.  Command
registration is handled separately via
:func:`~negotiation.slack.commands.register_commands` so the app
and commands are independently testable.
"""

from __future__ import annotations

import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


def create_slack_app(bot_token: str | None = None) -> App:
    """Create a Slack Bolt App instance.

    Args:
        bot_token: The Slack Bot User OAuth Token.  Falls back to the
            ``SLACK_BOT_TOKEN`` environment variable if not provided.

    Returns:
        A configured Bolt ``App`` instance.
    """
    return App(token=bot_token or os.environ["SLACK_BOT_TOKEN"])


def start_slack_app(app: App, app_token: str | None = None) -> None:
    """Start the Slack app in Socket Mode.

    Args:
        app: The Bolt ``App`` instance to start.
        app_token: The Slack App-Level Token with ``connections:write``
            scope.  Falls back to ``SLACK_APP_TOKEN`` environment
            variable if not provided.
    """
    handler = SocketModeHandler(app, app_token or os.environ["SLACK_APP_TOKEN"])
    handler.start()  # type: ignore[no-untyped-call]
