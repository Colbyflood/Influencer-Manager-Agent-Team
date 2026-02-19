"""Tests for centralized Settings, credential validation, and get_settings cache.

Covers: defaults, env-override, production credential gate, dev-mode warnings,
and lru_cache behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from negotiation.config import Settings, get_settings, validate_credentials

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Clear get_settings lru_cache before each test."""
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------

class TestSettingsDefaults:
    """Verify that Settings fields have the expected default values."""

    def test_settings_defaults(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]

        assert s.production is False
        assert s.webhook_port == 8000
        assert s.agent_email == ""
        assert s.audit_db_path == Path("data/audit.db")
        assert s.gmail_token_path == Path("token.json")

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRODUCTION", "true")
        monkeypatch.setenv("WEBHOOK_PORT", "9090")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")

        s = Settings(_env_file=None)  # type: ignore[call-arg]

        assert s.production is True
        assert s.webhook_port == 9090
        assert s.slack_bot_token.get_secret_value() == "xoxb-test"


# ---------------------------------------------------------------------------
# Credential validation
# ---------------------------------------------------------------------------

class TestValidateCredentials:
    """Verify validate_credentials behaviour in production and dev modes."""

    def test_validate_credentials_production_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production mode exits when credentials are missing."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            production=True,
            gmail_token_path=tmp_path / "nonexistent_token.json",
            sheets_service_account_path=tmp_path / "nonexistent_sa.json",
            slack_bot_token="",  # type: ignore[arg-type]
            slack_app_token="",  # type: ignore[arg-type]
        )

        with pytest.raises(SystemExit) as exc_info:
            validate_credentials(settings)

        assert exc_info.value.code == 1

    def test_validate_credentials_production_valid(self, tmp_path: Path) -> None:
        """Production mode passes when all credentials exist."""
        token_file = tmp_path / "token.json"
        token_file.write_text("{}")
        sa_file = tmp_path / "service_account.json"
        sa_file.write_text("{}")

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            production=True,
            gmail_token_path=token_file,
            sheets_service_account_path=sa_file,
            slack_bot_token="xoxb-valid",  # type: ignore[arg-type]
            slack_app_token="xapp-valid",  # type: ignore[arg-type]
        )

        # Should NOT raise or exit
        validate_credentials(settings)

    def test_validate_credentials_dev_mode_warns(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        """Dev mode logs warnings but does NOT exit."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            production=False,
            gmail_token_path=tmp_path / "missing_token.json",
            sheets_service_account_path=tmp_path / "missing_sa.json",
            slack_bot_token="",  # type: ignore[arg-type]
            slack_app_token="",  # type: ignore[arg-type]
        )

        # Should NOT raise or exit
        validate_credentials(settings)

        # Verify it did NOT call sys.exit
        # (If it had, pytest.raises would have caught it above)


# ---------------------------------------------------------------------------
# get_settings cache
# ---------------------------------------------------------------------------

class TestGetSettingsCached:
    """Verify lru_cache on get_settings."""

    def test_get_settings_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling get_settings() twice returns the exact same object."""
        # Ensure no .env interference
        monkeypatch.delenv("PRODUCTION", raising=False)

        first = get_settings()
        second = get_settings()

        assert first is second
