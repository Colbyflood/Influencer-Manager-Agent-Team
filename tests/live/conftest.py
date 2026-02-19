"""Shared fixtures for live integration tests.

Provides session-scoped fixtures that create real service clients using
credentials from environment variables (via Settings). Each fixture skips
the test if the required credentials are not available.
"""

from __future__ import annotations

import pytest

from negotiation.config import Settings


@pytest.fixture(scope="session")
def _live_settings() -> Settings:
    """Load application settings from environment for live tests."""
    return Settings()


@pytest.fixture(scope="session")
def agent_email(_live_settings: Settings) -> str:
    """Return the configured agent email address, skip if not set."""
    if not _live_settings.agent_email:
        pytest.skip("AGENT_EMAIL not configured")
    return _live_settings.agent_email


@pytest.fixture(scope="session")
def gmail_client(_live_settings: Settings):
    """Create a real GmailClient using OAuth2 credentials.

    Skips if the Gmail token file does not exist.
    """
    if not _live_settings.gmail_token_path.exists():
        pytest.skip("Gmail token not available")

    from negotiation.auth.credentials import get_gmail_service
    from negotiation.email.client import GmailClient

    service = get_gmail_service()
    return GmailClient(service, _live_settings.agent_email)


@pytest.fixture(scope="session")
def sheets_client(_live_settings: Settings):
    """Create a real SheetsClient using service account credentials.

    Skips if the Sheets key or service account path is not configured.
    """
    if not _live_settings.google_sheets_key:
        pytest.skip("GOOGLE_SHEETS_KEY not configured")

    sa_path = _live_settings.sheets_service_account_path.expanduser()
    if not sa_path.exists():
        pytest.skip(f"Sheets service account file not found: {sa_path}")

    from negotiation.auth.credentials import get_sheets_client
    from negotiation.sheets.client import SheetsClient

    gc = get_sheets_client(str(sa_path))
    return SheetsClient(gc, _live_settings.google_sheets_key)


@pytest.fixture(scope="session")
def slack_notifier(_live_settings: Settings):
    """Create a real SlackNotifier using the bot token from environment.

    Skips if the Slack bot token is not configured.
    """
    token = _live_settings.slack_bot_token.get_secret_value()
    if not token:
        pytest.skip("SLACK_BOT_TOKEN not configured")

    from negotiation.slack.client import SlackNotifier

    return SlackNotifier(
        escalation_channel=_live_settings.slack_escalation_channel,
        agreement_channel=_live_settings.slack_agreement_channel,
        bot_token=token,
    )
