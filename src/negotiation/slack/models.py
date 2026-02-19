"""Slack-specific configuration models.

Defines Pydantic models for Slack integration settings including
channel IDs and default mention users.
"""

from pydantic import BaseModel, Field


class SlackConfig(BaseModel):
    """Configuration for Slack integration.

    Stores channel IDs for routing messages and default mention users
    for agreement notifications.
    """

    escalation_channel: str = Field(description="Channel ID for escalation messages")
    agreement_channel: str = Field(description="Channel ID for agreement alerts")
    default_mention_users: list[str] = Field(
        default_factory=list,
        description="Default Slack user IDs to @ mention on agreements",
    )
