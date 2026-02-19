"""Slack integration package for influencer negotiation agent.

Provides Slack notification client, Block Kit message builders,
configuration models, escalation trigger engine with YAML config loading,
human takeover detection, thread state management, slash command handlers,
and Bolt app initialization.
"""

from negotiation.slack.app import create_slack_app, start_slack_app
from negotiation.slack.blocks import build_agreement_blocks, build_escalation_blocks
from negotiation.slack.client import SlackNotifier
from negotiation.slack.commands import register_commands
from negotiation.slack.dispatcher import SlackDispatcher
from negotiation.slack.models import SlackConfig
from negotiation.slack.takeover import ThreadStateManager, detect_human_reply
from negotiation.slack.triggers import (
    EscalationTriggersConfig,
    TriggerClassification,
    TriggerConfig,
    TriggerResult,
    TriggerType,
    classify_triggers,
    evaluate_triggers,
    load_triggers_config,
)

__all__ = [
    "EscalationTriggersConfig",
    "SlackConfig",
    "SlackDispatcher",
    "SlackNotifier",
    "ThreadStateManager",
    "TriggerClassification",
    "TriggerConfig",
    "TriggerResult",
    "TriggerType",
    "build_agreement_blocks",
    "build_escalation_blocks",
    "classify_triggers",
    "create_slack_app",
    "detect_human_reply",
    "evaluate_triggers",
    "load_triggers_config",
    "register_commands",
    "start_slack_app",
]
