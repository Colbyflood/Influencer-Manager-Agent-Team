"""Tests for application entry point: structlog config, service initialization, and app creation."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import structlog
from fastapi import FastAPI
from pydantic import SecretStr

from negotiation.app import configure_logging, create_app, initialize_services
from negotiation.config import Settings


def _reset_structlog() -> None:
    """Reset structlog so cached loggers don't leak between tests."""
    structlog.reset_defaults()


def _base_settings(tmp_path: Path, **overrides) -> Settings:
    """Build a Settings instance pointing audit_db to tmp_path.

    By default all optional credentials are empty so no external services
    are initialized.  Pass keyword overrides to customise.
    """
    defaults = {
        "audit_db_path": tmp_path / "audit.db",
        "gmail_token_path": tmp_path / "nonexistent-token.json",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[call-arg]


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

    def test_production_true_activates_json_renderer(self) -> None:
        """Passing production=True enables JSON rendering (caller reads from Settings)."""
        _reset_structlog()
        configure_logging(production=True)
        config = structlog.get_config()
        processors = config["processors"]
        assert any(
            isinstance(p, structlog.processors.JSONRenderer) for p in processors
        )

    def test_default_is_development_mode(self) -> None:
        _reset_structlog()
        configure_logging()
        config = structlog.get_config()
        processors = config["processors"]
        assert any(isinstance(p, structlog.dev.ConsoleRenderer) for p in processors)


class TestInitializeServices:
    """Tests for service initialization with mocked external dependencies."""

    def test_creates_audit_db_connection(self, tmp_path: Path) -> None:
        _reset_structlog()
        configure_logging(production=False)
        audit_path = tmp_path / "test_audit.db"
        settings = _base_settings(tmp_path, audit_db_path=audit_path)

        services = initialize_services(settings)

        assert services["audit_conn"] is not None
        assert services["audit_logger"] is not None
        assert audit_path.exists()

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_audit_db_path_setting_respected(self, tmp_path: Path) -> None:
        _reset_structlog()
        configure_logging(production=False)
        custom_path = tmp_path / "custom" / "audit.db"
        settings = _base_settings(tmp_path, audit_db_path=custom_path)

        services = initialize_services(settings)

        assert custom_path.exists()
        assert custom_path.parent.exists()

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_slack_notifier_none_when_no_token(self, tmp_path: Path) -> None:
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)

        assert services["slack_notifier"] is None
        assert services["bolt_app"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_configures_error_notifier_when_slack_available(
        self, tmp_path: Path
    ) -> None:
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(
            tmp_path,
            slack_bot_token=SecretStr("xoxb-test-token"),
            slack_escalation_channel="C12345",
            slack_agreement_channel="C67890",
        )

        mock_notifier_instance = MagicMock()
        mock_bolt_app = MagicMock()

        with patch("negotiation.slack.client.SlackNotifier", return_value=mock_notifier_instance), \
             patch("negotiation.app.configure_error_notifier") as mock_cfg_notifier, \
             patch("negotiation.app.create_slack_app", return_value=mock_bolt_app):
            services = initialize_services(settings)

            mock_cfg_notifier.assert_called_once_with(mock_notifier_instance)
            assert services["slack_notifier"] is mock_notifier_instance

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_sheets_client_none_when_no_key(self, tmp_path: Path) -> None:
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)

        assert services["sheets_client"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_gmail_client_initialized_with_token(self, tmp_path: Path) -> None:
        """GmailClient is created when gmail_token_path exists."""
        _reset_structlog()
        configure_logging(production=False)
        token_path = tmp_path / "token.json"
        token_path.write_text("{}")  # file must exist
        settings = _base_settings(
            tmp_path,
            gmail_token_path=token_path,
            agent_email="agent@example.com",
        )

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
            services = initialize_services(settings)
            assert services["gmail_client"] is mock_gmail_client

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_gmail_client_none_without_token(self, tmp_path: Path) -> None:
        """GmailClient is None when gmail_token_path does not exist."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)

        assert services["gmail_client"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_anthropic_client_initialized_with_api_key(self, tmp_path: Path) -> None:
        """Anthropic client is created when anthropic_api_key is set."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(
            tmp_path,
            anthropic_api_key=SecretStr("test-key"),
        )

        mock_client = MagicMock()

        with patch(
            "negotiation.llm.client.get_anthropic_client",
            return_value=mock_client,
        ):
            services = initialize_services(settings)
            assert services["anthropic_client"] is mock_client

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_anthropic_client_none_without_key(self, tmp_path: Path) -> None:
        """Anthropic client is None when anthropic_api_key is not set."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)

        assert services["anthropic_client"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_slack_dispatcher_initialized_when_notifier_available(
        self, tmp_path: Path
    ) -> None:
        """SlackDispatcher is created when SlackNotifier and ThreadStateManager exist."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(
            tmp_path,
            slack_bot_token=SecretStr("xoxb-test"),
            agent_email="agent@example.com",
        )

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
            services = initialize_services(settings)
            assert services["slack_dispatcher"] is mock_dispatcher

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_slack_dispatcher_none_without_notifier(self, tmp_path: Path) -> None:
        """SlackDispatcher is None when SlackNotifier is unavailable."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)

        assert services["slack_dispatcher"] is None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])


class TestCreateApp:
    """Tests for FastAPI app creation."""

    def test_returns_fastapi_instance(self, tmp_path: Path) -> None:
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)
        app = create_app(services)

        assert isinstance(app, FastAPI)

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_create_app_uses_lifespan(self, tmp_path: Path) -> None:
        """FastAPI app uses lifespan context manager instead of on_event."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)
        app = create_app(services)

        assert app.router.lifespan_context is not None

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_no_deprecated_on_event(self) -> None:
        """Verify deprecated on_event pattern is not used in create_app."""
        source = inspect.getsource(create_app)
        assert "on_event" not in source

    def test_gmail_webhook_route_exists(self, tmp_path: Path) -> None:
        """Verify /webhooks/gmail endpoint is registered."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)
        app = create_app(services)

        route_paths = [route.path for route in app.routes]
        assert "/webhooks/gmail" in route_paths

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])

    def test_settings_stored_on_app_state(self, tmp_path: Path) -> None:
        """Verify app.state.settings is set for use by webhook endpoints."""
        _reset_structlog()
        configure_logging(production=False)
        settings = _base_settings(tmp_path)

        services = initialize_services(settings)
        app = create_app(services)

        assert hasattr(app.state, "settings")
        assert isinstance(app.state.settings, Settings)

        from negotiation.audit.store import close_audit_db

        close_audit_db(services["audit_conn"])


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
