"""Slack integration package for influencer negotiation agent.

Provides Slack notification client, Block Kit message builders,
configuration models, human takeover detection, thread state management,
slash command handlers, and Bolt app initialization.
"""

from negotiation.slack.app import create_slack_app, start_slack_app
from negotiation.slack.blocks import build_agreement_blocks, build_escalation_blocks
from negotiation.slack.client import SlackNotifier
from negotiation.slack.commands import register_commands
from negotiation.slack.models import SlackConfig
from negotiation.slack.takeover import ThreadStateManager, detect_human_reply

__all__ = [
    "SlackConfig",
    "SlackNotifier",
    "ThreadStateManager",
    "build_agreement_blocks",
    "build_escalation_blocks",
    "create_slack_app",
    "detect_human_reply",
    "register_commands",
    "start_slack_app",
]
