"""Tests for application entry point: structlog config, service initialization, and app creation."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import structlog
from fastapi import FastAPI

from negotiation.app import configure_logging, create_app, initialize_services


def _reset_structlog() -> None:
    """Reset structlog so cached loggers don't leak between tests."""
    structlog.reset_defaults()


def _clean_env(monkeypatch) -> None:
    """Remove all optional service env vars to ensure clean baseline."""
    for key in (
        "SLACK_BOT_TOKEN",
        "GOOGLE_SHEETS_KEY",
        "GMAIL_TOKEN_PATH",
        "ANTHROPIC_API_KEY",
        "AGENT_EMAIL",
    ):
        monkeypatch.delenv(key, raising=False)


class TestConfigureLogging:
    """Tests for structlog configuration in dev and production modes."""

    def test_development_mode_uses_console_renderer(self) -> None:
        _reset_structlog()
        configure_logging(production=False)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)

    def test_production_mode_uses_json_renderer(self) -> None:
        _reset_structlog()
        configure_logging(production=True)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            isinstance(p, structlog.processors.JSONRenderer) for p in processors
        )

    def test_production_env_var_activates_production_mode(self, monkeypatch) -> None:
        _reset_structlog()
        monkeypatch.setenv("PRODUCTION", "true")
        configure_logging()
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            isinstance(p, structlog.processors.JSONRenderer) for p in processors
        )

    def test_no_production_env_defaults_to_dev(self, monkeypatch) -> None:
        _reset_structlog()
        monkeypatch.delenv("PRODUCTION", raising=False)
        configure_logging()
        config = structlog.get_config()
        processors = config["processors"]
        assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)


class TestInitializeServices:
    """Tests for service initialization with mocked external dependencies."""

    def test_creates_audit_db_connection(self, tmp_path: Path, monkeypatch) -> None:
        _reset_structlog()
        configure_logging(production=False)
        audit_path = tmp_path / "test_audit.db"
        monkeypatch.setenv("AUDIT_DB_PATH", str(audit_path))
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_SHEETS_KEY", raising=False)

        services = initialize_services()

        assert services["audit_conn"] is not None
        assert services["audit_logger"] is not None
        assert audit_path.exists()

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_audit_db_path_env_var_respected(self, tmp_path: Path, monkeypatch) -> None:
        _reset_structlog()
        configure_logging(production=False)
        custom_path = tmp_path / "custom" / "audit.db"
        monkeypatch.setenv("AUDIT_DB_PATH", str(custom_path))
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_SHEETS_KEY", raising=False)

        services = initialize_services()

        assert custom_path.exists()
        assert custom_path.parent.exists()

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_slack_notifier_none_when_no_token(self, tmp_path: Path, monkeypatch) -> None:
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_SHEETS_KEY", raising=False)

        services = initialize_services()

        assert services["slack_notifier"] is None
        assert services["bolt_app"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_configures_error_notifier_when_slack_available(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_ESCALATION_CHANNEL", "C12345")
        monkeypatch.setenv("SLACK_AGREEMENT_CHANNEL", "C67890")
        monkeypatch.delenv("GOOGLE_SHEETS_KEY", raising=False)

        mock_notifier_instance = MagicMock()
        mock_bolt_app = MagicMock()

        with patch("negotiation.slack.client.SlackNotifier", return_value=mock_notifier_instance), \
             patch("negotiation.app.configure_error_notifier") as mock_cfg_notifier, \
             patch("negotiation.app.create_slack_app", return_value=mock_bolt_app):
            services = initialize_services()

            mock_cfg_notifier.assert_called_once_with(mock_notifier_instance)
            assert services["slack_notifier"] is mock_notifier_instance

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_sheets_client_none_when_no_key(self, tmp_path: Path, monkeypatch) -> None:
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_SHEETS_KEY", raising=False)

        services = initialize_services()

        assert services["sheets_client"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_gmail_client_initialized_with_token(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """GmailClient is created when GMAIL_TOKEN_PATH is set."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "token.json"))
        monkeypatch.setenv("AGENT_EMAIL", "agent@example.com")
        _clean_env(monkeypatch)
        # Re-set the ones we need after clean
        monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "token.json"))
        monkeypatch.setenv("AGENT_EMAIL", "agent@example.com")

        mock_service = MagicMock()
        mock_gmail_client = MagicMock()

        with (
            patch(
                "negotiation.auth.credentials.get_gmail_service",
                return_value=mock_service,
            ),
            patch(
                "negotiation.email.client.GmailClient",
                return_value=mock_gmail_client,
            ),
        ):
            services = initialize_services()
            assert services["gmail_client"] is mock_gmail_client

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_gmail_client_none_without_token(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """GmailClient is None when GMAIL_TOKEN_PATH is not set."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)

        services = initialize_services()

        assert services["gmail_client"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_anthropic_client_initialized_with_api_key(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Anthropic client is created when ANTHROPIC_API_KEY is set."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        mock_client = MagicMock()

        with patch(
            "negotiation.llm.client.get_anthropic_client",
            return_value=mock_client,
        ):
            services = initialize_services()
            assert services["anthropic_client"] is mock_client

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_anthropic_client_none_without_key(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Anthropic client is None when ANTHROPIC_API_KEY is not set."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)

        services = initialize_services()

        assert services["anthropic_client"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_slack_dispatcher_initialized_when_notifier_available(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """SlackDispatcher is created when SlackNotifier and ThreadStateManager exist."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("AGENT_EMAIL", "agent@example.com")

        mock_notifier = MagicMock()
        mock_bolt_app = MagicMock()
        mock_dispatcher = MagicMock()

        with (
            patch(
                "negotiation.slack.client.SlackNotifier",
                return_value=mock_notifier,
            ),
            patch(
                "negotiation.app.create_slack_app",
                return_value=mock_bolt_app,
            ),
            patch(
                "negotiation.slack.dispatcher.SlackDispatcher",
                return_value=mock_dispatcher,
            ),
        ):
            services = initialize_services()
            assert services["slack_dispatcher"] is mock_dispatcher

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_slack_dispatcher_none_without_notifier(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """SlackDispatcher is None when SlackNotifier is unavailable."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)

        services = initialize_services()

        assert services["slack_dispatcher"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])


class TestCreateApp:
    """Tests for FastAPI app creation."""

    def test_returns_fastapi_instance(self, tmp_path: Path, monkeypatch) -> None:
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)

        services = initialize_services()
        app = create_app(services)

        assert isinstance(app, FastAPI)

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_create_app_uses_lifespan(self, tmp_path: Path, monkeypatch) -> None:
        """FastAPI app uses lifespan context manager instead of on_event."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)

        services = initialize_services()
        app = create_app(services)

        assert app.router.lifespan_context is not None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_no_deprecated_on_event(self) -> None:
        """Verify deprecated on_event pattern is not used in create_app."""
        source = inspect.getsource(create_app)
        assert "on_event" not in source

    def test_gmail_webhook_route_exists(self, tmp_path: Path, monkeypatch) -> None:
        """Verify /webhooks/gmail endpoint is registered."""
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        _clean_env(monkeypatch)

        services = initialize_services()
        app = create_app(services)

        route_paths = [route.path for route in app.routes]
        assert "/webhooks/gmail" in route_paths

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])


class TestWebhookPortEnvVar:
    """Tests for WEBHOOK_PORT environment variable."""

    def test_webhook_port_env_var_is_respected(self, monkeypatch) -> None:
        monkeypatch.setenv("WEBHOOK_PORT", "9999")
        assert int(os.environ["WEBHOOK_PORT"]) == 9999


class TestMainImport:
    """Test that main() can be imported without side effects."""

    def test_main_importable(self) -> None:
        from negotiation.app import main

        assert callable(main)

    def test_configure_logging_importable(self) -> None:
        from negotiation.app import configure_logging

        assert callable(configure_logging)

    def test_initialize_services_importable(self) -> None:
        from negotiation.app import initialize_services

        assert callable(initialize_services)
