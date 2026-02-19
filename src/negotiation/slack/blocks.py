"""Block Kit message builders for Slack notifications.

Pure functions that return Block Kit block dicts for escalation and agreement
messages. These functions have no side effects and are easy to test.
"""

from decimal import Decimal
from typing import Any


def build_escalation_blocks(
    influencer_name: str,
    influencer_email: str,
    client_name: str,
    escalation_reason: str,
    evidence_quote: str,
    proposed_rate: str | None,
    our_rate: str | None,
    suggested_actions: list[str],
    details_link: str,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an escalation message.

    Returns a list of Block Kit block dicts ready for chat_postMessage.
    Conditional sections (rate comparison, evidence, suggested actions)
    are only included when the corresponding data is provided.

    Args:
        influencer_name: Name of the influencer being escalated.
        influencer_email: Influencer's email address.
        client_name: Client/brand name.
        escalation_reason: Why escalation was triggered (specific trigger + context).
        evidence_quote: Quote from the email that triggered escalation.
        proposed_rate: Influencer's proposed rate as string, or None.
        our_rate: Our counter-offer rate as string, or None.
        suggested_actions: List of suggested actions for the reviewer.
        details_link: URL to full conversation details (Gmail thread permalink).

    Returns:
        List of Block Kit block dicts.
    """
    blocks: list[dict[str, Any]] = [
        # Header
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Escalation: {influencer_name}"},
        },
        # Key details as fields
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Influencer:*\n{influencer_name}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{influencer_email}"},
                {"type": "mrkdwn", "text": f"*Client:*\n{client_name}"},
                {"type": "mrkdwn", "text": f"*Reason:*\n{escalation_reason}"},
            ],
        },
    ]

    # Rate comparison (only if rates available)
    if proposed_rate or our_rate:
        blocks.append(
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Their Rate:*\n${proposed_rate or 'N/A'}"},
                    {"type": "mrkdwn", "text": f"*Our Rate:*\n${our_rate or 'N/A'}"},
                ],
            }
        )

    # Evidence quote
    if evidence_quote:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Evidence:*\n>{evidence_quote}",
                },
            }
        )

    # Suggested actions
    if suggested_actions:
        actions_text = "\n".join(f"- {action}" for action in suggested_actions)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggested Actions:*\n{actions_text}",
                },
            }
        )

    # Link to full details
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<{details_link}|View full conversation details>",
                },
            ],
        }
    )

    return blocks


def build_agreement_blocks(
    influencer_name: str,
    influencer_email: str,
    client_name: str,
    agreed_rate: Decimal,
    platform: str,
    deliverables: str,
    cpm_achieved: Decimal,
    next_steps: list[str],
    mention_users: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an agreement alert.

    Returns a list of Block Kit block dicts ready for chat_postMessage.
    Conditional sections (next steps, mentions) are only included when
    the corresponding data is provided.

    Args:
        influencer_name: Name of the influencer.
        influencer_email: Influencer's email address.
        client_name: Client/brand name.
        agreed_rate: The agreed-upon rate.
        platform: Social media platform.
        deliverables: Description of agreed deliverables.
        cpm_achieved: CPM achieved with the agreed rate.
        next_steps: List of next steps after agreement.
        mention_users: Slack user IDs to @ mention, or None.

    Returns:
        List of Block Kit block dicts.
    """
    blocks: list[dict[str, Any]] = [
        # Header
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Deal Agreed: {influencer_name}"},
        },
        # Key details as fields
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Influencer:*\n{influencer_name}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{influencer_email}"},
                {"type": "mrkdwn", "text": f"*Client:*\n{client_name}"},
                {"type": "mrkdwn", "text": f"*Platform:*\n{platform.title()}"},
            ],
        },
        # Financial details
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Agreed Rate:*\n${agreed_rate:,.2f}"},
                {"type": "mrkdwn", "text": f"*CPM Achieved:*\n${cpm_achieved:,.2f}"},
                {"type": "mrkdwn", "text": f"*Deliverables:*\n{deliverables}"},
            ],
        },
    ]

    # Next steps
    if next_steps:
        steps_text = "\n".join(f"- {step}" for step in next_steps)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Next Steps:*\n{steps_text}",
                },
            }
        )

    # Campaign mentions
    if mention_users:
        mention_text = " ".join(f"<@{uid}>" for uid in mention_users)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": mention_text},
            }
        )

    return blocks
