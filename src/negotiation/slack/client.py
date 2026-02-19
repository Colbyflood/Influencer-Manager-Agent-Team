"""Slack notification client for posting escalation and agreement messages.

Wraps slack_sdk.WebClient to provide typed methods for posting Block Kit
messages to designated channels.
"""

from __future__ import annotations

import os
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifier:
    """Posts structured notifications to Slack channels.

    Uses the Slack WebClient with Block Kit messages for rich formatting.
    Requires SLACK_BOT_TOKEN environment variable or explicit bot_token.
    """

    def __init__(
        self,
        escalation_channel: str,
        agreement_channel: str,
        bot_token: str | None = None,
    ) -> None:
        """Initialize the SlackNotifier.

        Args:
            escalation_channel: Channel ID for escalation messages.
            agreement_channel: Channel ID for agreement alerts.
            bot_token: Slack bot token. Falls back to SLACK_BOT_TOKEN env var.

        Raises:
            KeyError: If bot_token is None and SLACK_BOT_TOKEN is not set.
        """
        token = bot_token or os.environ["SLACK_BOT_TOKEN"]
        self._client = WebClient(token=token)
        self._escalation_channel = escalation_channel
        self._agreement_channel = agreement_channel

    def post_escalation(self, blocks: list[dict[str, Any]], fallback_text: str) -> str:
        """Post an escalation message to the escalation channel.

        Args:
            blocks: Block Kit blocks for the message.
            fallback_text: Plain-text fallback for notifications.

        Returns:
            The Slack message timestamp (ts) for reference.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        response = self._client.chat_postMessage(
            channel=self._escalation_channel,
            blocks=blocks,
            text=fallback_text,
        )
        return str(response["ts"])

    def post_agreement(self, blocks: list[dict[str, Any]], fallback_text: str) -> str:
        """Post an agreement alert to the agreement channel.

        Args:
            blocks: Block Kit blocks for the message.
            fallback_text: Plain-text fallback for notifications.

        Returns:
            The Slack message timestamp (ts) for reference.

        Raises:
            SlackApiError: If the Slack API call fails.
        """
        response = self._client.chat_postMessage(
            channel=self._agreement_channel,
            blocks=blocks,
            text=fallback_text,
        )
        return str(response["ts"])


__all__ = ["SlackApiError", "SlackNotifier"]
