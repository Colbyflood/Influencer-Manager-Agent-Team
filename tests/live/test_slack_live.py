"""Live integration tests for Slack API operations.

These tests post real messages to Slack channels and verify the API
responds successfully. They require SLACK_BOT_TOKEN and channel
configuration in environment variables.

Run with: pytest -m live -k slack
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.mark.live
def test_slack_post_message(slack_notifier):
    """Post a test message to the escalation channel and verify success.

    Uses the underlying WebClient directly to post a clearly-identified
    test message so operators know it is automated.
    """
    timestamp = datetime.now(tz=UTC).isoformat()
    test_text = f"[LIVE TEST] Slack integration check at {timestamp}"

    response = slack_notifier._client.chat_postMessage(
        channel=slack_notifier._escalation_channel,
        text=test_text,
    )

    assert response["ok"] is True, f"Expected Slack response ok=True, got: {response['ok']}"
    assert "ts" in response, f"Expected 'ts' in Slack response, got keys: {list(response.keys())}"
