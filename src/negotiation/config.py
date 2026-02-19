"""Centralized, typed configuration using pydantic-settings.

Provides a single ``Settings`` class backed by ``.env`` file and environment
variables, a cached ``get_settings()`` accessor, and a ``validate_credentials()``
startup gate that enforces credential presence in production mode.

IMPORTANT: This module has ZERO imports from the ``negotiation`` package to
prevent circular imports.  Only stdlib, pydantic, pydantic_settings, and
structlog are used.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import structlog
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger()


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env`` file.

    All 15+ environment variables previously scattered across 6 source files
    are consolidated here with typed defaults.  ``SecretStr`` fields prevent
    accidental leaks in logs or error output.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- General ---------------------------------------------------------------
    production: bool = False
    webhook_port: int = 8000
    agent_email: str = ""

    # -- Audit -----------------------------------------------------------------
    audit_db_path: Path = Path("data/audit.db")

    # -- Gmail -----------------------------------------------------------------
    gmail_token_path: Path = Path("token.json")
    gmail_credentials_path: Path = Path("credentials.json")
    gmail_pubsub_topic: str = ""

    # -- Google Sheets ---------------------------------------------------------
    google_sheets_key: str = ""
    sheets_service_account_path: Path = Path("~/.config/gspread/service_account.json")

    # -- Slack (secrets) -------------------------------------------------------
    slack_bot_token: SecretStr = SecretStr("")
    slack_app_token: SecretStr = SecretStr("")
    slack_escalation_channel: str = ""
    slack_agreement_channel: str = ""

    # -- LLM / Anthropic -------------------------------------------------------
    anthropic_api_key: SecretStr = SecretStr("")

    # -- ClickUp ---------------------------------------------------------------
    clickup_api_token: str = ""
    clickup_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    The ``@lru_cache`` decorator ensures environment variables are parsed
    exactly once.  Call ``get_settings.cache_clear()`` in tests to reset.

    Returns:
        The application ``Settings``.
    """
    try:
        return Settings()
    except ValidationError as exc:
        # Log only the structured errors list -- never the full exception
        # which may contain raw SecretStr values.
        logger.error("settings_validation_failed", errors=exc.errors())
        sys.exit(1)


def validate_credentials(settings: Settings) -> None:
    """Enforce credential presence at startup.

    In **production** mode (``settings.production is True``), the application
    exits with a clear error block if any required credential is missing.

    In **development** mode, each missing credential is logged as a warning
    but the application continues to start.

    Args:
        settings: The loaded application settings.
    """
    errors: list[str] = []

    # Gmail token file
    if not settings.gmail_token_path.exists():
        errors.append(f"Gmail token file not found: {settings.gmail_token_path}")

    # Sheets service account file
    sa_path = settings.sheets_service_account_path.expanduser()
    if not sa_path.exists():
        errors.append(f"Sheets service account file not found: {sa_path}")

    # Slack bot token
    if not settings.slack_bot_token.get_secret_value():
        errors.append("SLACK_BOT_TOKEN is empty or not set")

    # Slack app token
    if not settings.slack_app_token.get_secret_value():
        errors.append("SLACK_APP_TOKEN is empty or not set")

    if not errors:
        logger.info("credential_validation_passed")
        return

    if settings.production:
        for err in errors:
            logger.error("credential_missing", detail=err)
        print("\n=== STARTUP FAILED ===", file=sys.stderr)
        print("Missing required credentials for production mode:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print("======================\n", file=sys.stderr)
        sys.exit(1)
    else:
        for err in errors:
            logger.warning("credential_missing_dev", detail=err)
