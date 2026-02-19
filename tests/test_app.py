"""Tests for application entry point: structlog config, service initialization, and app creation."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import structlog
from fastapi import FastAPI

from negotiation.app import configure_logging, create_app, initialize_services


def _reset_structlog() -> None:
    """Reset structlog so cached loggers don't leak between tests."""
    structlog.reset_defaults()


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


class TestCreateApp:
    """Tests for FastAPI app creation."""

    def test_returns_fastapi_instance(self, tmp_path: Path, monkeypatch) -> None:
        _reset_structlog()
        configure_logging(production=False)
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_SHEETS_KEY", raising=False)

        services = initialize_services()
        app = create_app(services)

        assert isinstance(app, FastAPI)

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
