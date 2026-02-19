"""Live integration tests for Gmail API operations.

These tests send real emails via the Gmail API and verify delivery.
They require valid OAuth2 credentials (token.json) and AGENT_EMAIL
to be configured in environment variables.

Run with: pytest -m live -k gmail
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

import pytest

from negotiation.email.models import OutboundEmail


@pytest.mark.live
def test_gmail_send_and_receive(gmail_client, agent_email):
    """Send an email to self and verify the API returns a valid response."""
    unique_subject = f"[LIVE TEST] Gmail send {datetime.now(tz=UTC).isoformat()}"

    result = gmail_client.send(
        OutboundEmail(
            to=agent_email,
            subject=unique_subject,
            body="This is an automated live test email. Safe to delete.",
        )
    )

    assert "id" in result, f"Expected 'id' in send response, got: {result}"
    assert "threadId" in result, f"Expected 'threadId' in send response, got: {result}"

    # Brief wait for delivery (send-to-self is near-instant on Gmail)
    time.sleep(3)


@pytest.mark.live
def test_gmail_watch_setup(gmail_client):
    """Verify Gmail push notification watch can be established.

    Only runs when GMAIL_PUBSUB_TOPIC is set (e.g.
    'projects/my-project/topics/gmail-notifications').
    """
    topic = os.environ.get("GMAIL_PUBSUB_TOPIC", "")
    if not topic:
        pytest.skip("GMAIL_PUBSUB_TOPIC not configured")

    result = gmail_client.setup_watch(topic)

    assert "historyId" in result, f"Expected 'historyId' in watch response, got: {result}"
    assert "expiration" in result, f"Expected 'expiration' in watch response, got: {result}"
