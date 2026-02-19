"""Tests for SlackNotifier client.

Uses mocked WebClient to verify correct channel routing and
message posting without requiring Slack API access.
"""

from unittest.mock import MagicMock

from negotiation.slack.client import SlackNotifier


def _create_notifier_with_mock():
    """Create a SlackNotifier with a mocked WebClient."""
    notifier = SlackNotifier(
        escalation_channel="C_ESCALATION",
        agreement_channel="C_AGREEMENTS",
        bot_token="xoxb-test-token",
    )
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
    notifier._client = mock_client
    return notifier, mock_client


def test_post_escalation_calls_correct_channel():
    """Escalation messages go to the escalation channel."""
    notifier, mock_client = _create_notifier_with_mock()

    test_blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]
    ts = notifier.post_escalation(
        blocks=test_blocks,
        fallback_text="Escalation: Test",
    )

    mock_client.chat_postMessage.assert_called_once_with(
        channel="C_ESCALATION",
        blocks=test_blocks,
        text="Escalation: Test",
    )
    assert ts == "1234567890.123456"


def test_post_agreement_calls_correct_channel():
    """Agreement messages go to the agreement channel."""
    notifier, mock_client = _create_notifier_with_mock()

    test_blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Deal"}}]
    ts = notifier.post_agreement(
        blocks=test_blocks,
        fallback_text="Deal Agreed: Test",
    )

    mock_client.chat_postMessage.assert_called_once_with(
        channel="C_AGREEMENTS",
        blocks=test_blocks,
        text="Deal Agreed: Test",
    )
    assert ts == "1234567890.123456"


def test_post_escalation_returns_timestamp():
    """post_escalation returns the message timestamp from Slack response."""
    notifier, mock_client = _create_notifier_with_mock()
    mock_client.chat_postMessage.return_value = {"ts": "9999999999.000001"}

    ts = notifier.post_escalation(blocks=[], fallback_text="test")

    assert ts == "9999999999.000001"


def test_post_agreement_returns_timestamp():
    """post_agreement returns the message timestamp from Slack response."""
    notifier, mock_client = _create_notifier_with_mock()
    mock_client.chat_postMessage.return_value = {"ts": "8888888888.000002"}

    ts = notifier.post_agreement(blocks=[], fallback_text="test")

    assert ts == "8888888888.000002"


def test_escalation_and_agreement_use_different_channels():
    """Escalation and agreement messages are routed to different channels."""
    notifier, mock_client = _create_notifier_with_mock()

    notifier.post_escalation(blocks=[], fallback_text="esc")
    esc_call = mock_client.chat_postMessage.call_args_list[0]

    mock_client.reset_mock()

    notifier.post_agreement(blocks=[], fallback_text="agr")
    agr_call = mock_client.chat_postMessage.call_args_list[0]

    assert esc_call.kwargs["channel"] == "C_ESCALATION"
    assert agr_call.kwargs["channel"] == "C_AGREEMENTS"
