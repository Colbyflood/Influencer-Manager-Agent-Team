"""Slack integration package for influencer negotiation agent.

Provides Slack notification client, Block Kit message builders,
and configuration models for escalation and agreement channels.
"""

from negotiation.slack.blocks import build_agreement_blocks, build_escalation_blocks
from negotiation.slack.client import SlackNotifier
from negotiation.slack.models import SlackConfig

__all__ = [
    "SlackConfig",
    "SlackNotifier",
    "build_agreement_blocks",
    "build_escalation_blocks",
]
