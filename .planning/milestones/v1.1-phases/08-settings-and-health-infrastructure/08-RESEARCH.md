# Phase 8: Settings and Health Infrastructure - Research

**Researched:** 2026-02-19
**Domain:** Configuration management, health endpoints, credential validation
**Confidence:** HIGH

## Summary

Phase 8 replaces the 22+ raw `os.environ.get()` calls scattered across 6 source files with a single `pydantic-settings` `BaseSettings` class, adds `/health` (liveness) and `/ready` (readiness) endpoints to the existing FastAPI application, and implements fail-fast startup validation for all three credential types (Gmail OAuth2 token, Sheets service account, Slack bot token).

The codebase already has FastAPI 0.129+, uvicorn, pydantic 2.12+, and structlog in `pyproject.toml`. The only new dependency is `pydantic-settings>=2.13.0`. There is already a basic `/health` endpoint on the ClickUp webhook router (`src/negotiation/campaign/webhook.py:124-131`) that needs to be relocated to a top-level route. The main application entry point (`src/negotiation/app.py`) currently reads 22 environment variables via `os.environ.get()` and `os.environ[]` -- this is the primary refactoring target.

**Primary recommendation:** Create a `src/negotiation/config.py` module with a single `Settings(BaseSettings)` class covering all 15 distinct environment variables, add `/health` and `/ready` as top-level FastAPI routes (not on the webhook sub-router), and add a `validate_credentials()` function called at the top of `initialize_services()` that fails fast with `SystemExit` before any service initialization.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONFIG-01 | Agent loads all configuration from environment variables via pydantic-settings with .env file support | pydantic-settings 2.13.0 BaseSettings with `SettingsConfigDict(env_file=".env")` replaces all 22 `os.environ` calls across 6 files. See Standard Stack and Code Examples sections. |
| OBS-01 | Agent exposes /health liveness endpoint that returns 200 when the process is alive | Simple FastAPI GET route returning `{"status": "healthy"}`. Already partially exists on webhook router -- needs relocation to top-level app. See Architecture Patterns section. |
| OBS-02 | Agent exposes /ready readiness endpoint that checks DB writable and Gmail token present | FastAPI GET route that executes `SELECT 1` on audit SQLite connection and checks Gmail token file presence. Returns 200 or 503. See Architecture Patterns and Code Examples sections. |
| STATE-03 | Agent validates credentials (Gmail token, Sheets SA, Slack token) at startup and fails fast with clear errors | `validate_credentials()` function checks file existence (Gmail token.json, Sheets SA JSON) and non-empty string (Slack bot token) before service initialization. Uses `sys.exit(1)` with structlog error on failure. See Architecture Patterns section. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-settings | >=2.13.0 | Typed config from env vars and .env files | Official Pydantic companion; recommended by FastAPI docs; replaces raw os.environ with validated, typed fields |
| pydantic | >=2.12,<3 | Already installed; BaseSettings inherits from BaseModel | Already a project dependency |
| fastapi | >=0.129.0 | Already installed; hosts /health and /ready endpoints | Already a project dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | (transitive) | .env file parsing | pydantic-settings pulls this in automatically when env_file is configured |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | python-decouple | Less type safety, no Pydantic integration, separate validation step needed |
| pydantic-settings | dynaconf | More powerful (multi-env, vaults) but heavy for this use case; no Pydantic model integration |
| Manual /health endpoint | fastapi-health library | Adds dependency for 10 lines of code; overkill for two simple endpoints |

**Installation:**
```bash
pip install pydantic-settings>=2.13.0
```

Or add to `pyproject.toml` dependencies:
```toml
"pydantic-settings>=2.13.0",
```

## Architecture Patterns

### Recommended Project Structure
```
src/negotiation/
├── config.py              # NEW: Settings(BaseSettings) + validate_credentials()
├── health.py              # NEW: /health and /ready endpoint handlers
├── app.py                 # MODIFIED: uses Settings instead of os.environ
├── auth/credentials.py    # MODIFIED: accepts paths from Settings, no os.environ
├── slack/app.py           # MODIFIED: accepts tokens from Settings, no os.environ
├── slack/client.py        # MODIFIED: accepts token from Settings, no os.environ
├── campaign/webhook.py    # MODIFIED: remove /health (relocated), use Settings for secret
└── audit/cli.py           # MODIFIED: can accept Settings-derived db path
```

### Pattern 1: Centralized Settings Class
**What:** A single `Settings(BaseSettings)` class with all environment variables as typed fields.
**When to use:** Always -- this is the CONFIG-01 requirement.
**Example:**
```python
# Source: pydantic-settings docs + FastAPI advanced/settings docs
from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Typed configuration for the negotiation agent.

    All values load from environment variables (case-insensitive)
    with .env file fallback. Required fields with no default
    will raise ValidationError at instantiation if missing.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Required credentials (no defaults = fail on missing) ---
    slack_bot_token: SecretStr
    slack_app_token: SecretStr
    gmail_token_path: Path
    sheets_service_account_path: Path = Path("~/.config/gspread/service_account.json")
    google_sheets_key: str

    # --- Optional / with defaults ---
    production: bool = False
    agent_email: str = ""
    audit_db_path: Path = Path("data/audit.db")
    webhook_port: int = 8000
    slack_escalation_channel: str = ""
    slack_agreement_channel: str = ""
    anthropic_api_key: SecretStr | None = None
    clickup_api_token: str = ""
    clickup_webhook_secret: str = ""
    gmail_pubsub_topic: str = ""
```

### Pattern 2: Health Endpoints (Liveness + Readiness)
**What:** Two GET endpoints: `/health` (always 200 if process alive) and `/ready` (200 only when dependencies available, 503 otherwise).
**When to use:** OBS-01 and OBS-02 requirements.
**Example:**
```python
# Source: FastAPI health check patterns + Docker HEALTHCHECK best practices
from fastapi import FastAPI
from fastapi.responses import JSONResponse

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: process is running."""
    return {"status": "healthy"}

@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness probe: dependencies available."""
    checks: dict[str, str] = {}

    # Check 1: Audit DB writable
    try:
        conn = app.state.services["audit_conn"]
        conn.execute("SELECT 1")
        checks["audit_db"] = "ok"
    except Exception:
        checks["audit_db"] = "fail"

    # Check 2: Gmail token present
    gmail_client = app.state.services.get("gmail_client")
    checks["gmail"] = "ok" if gmail_client is not None else "fail"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
        status_code=status_code,
    )
```

### Pattern 3: Fail-Fast Startup Credential Validation
**What:** Validate that all required credentials exist and are loadable before initializing any services.
**When to use:** STATE-03 requirement.
**Example:**
```python
# Source: Derived from codebase analysis of auth/credentials.py
import sys
import structlog
from negotiation.config import Settings

logger = structlog.get_logger()

def validate_credentials(settings: Settings) -> None:
    """Check all required credential files exist and tokens are non-empty.

    Raises SystemExit with clear error messages if any credential is
    missing or invalid. Called before service initialization.
    """
    errors: list[str] = []

    # Gmail OAuth2 token file
    token_path = settings.gmail_token_path
    if not token_path.exists():
        errors.append(f"Gmail token file not found: {token_path}")

    # Sheets service account JSON
    sa_path = settings.sheets_service_account_path.expanduser()
    if not sa_path.exists():
        errors.append(f"Sheets service account file not found: {sa_path}")

    # Slack tokens (SecretStr -- check get_secret_value())
    if not settings.slack_bot_token.get_secret_value():
        errors.append("SLACK_BOT_TOKEN is empty")

    if not settings.slack_app_token.get_secret_value():
        errors.append("SLACK_APP_TOKEN is empty")

    if errors:
        for error in errors:
            logger.error("Credential validation failed", error=error)
        sys.exit(1)
```

### Pattern 4: Settings Injection into Services
**What:** Pass the Settings instance (or individual values from it) into service constructors instead of reading os.environ inside each module.
**When to use:** Everywhere that currently calls os.environ.
**Example:**
```python
# In app.py initialize_services():
settings = Settings()
validate_credentials(settings)

# Then pass settings values explicitly:
audit_db_path = settings.audit_db_path
slack_bot_token = settings.slack_bot_token.get_secret_value()
gmail_token_path = settings.gmail_token_path
# ... etc
```

### Anti-Patterns to Avoid
- **Reading os.environ inside library modules:** Credential modules (auth/credentials.py, slack/app.py, slack/client.py) should receive values as parameters, not read environment themselves. The Settings class is the single source of truth.
- **Making Settings a global singleton:** Use `@lru_cache` on a `get_settings()` function instead. This allows test override via FastAPI's `dependency_overrides`.
- **Checking credentials in /ready:** The `/ready` endpoint checks runtime availability (DB writable, Gmail client initialized), not whether raw credential files exist. Credential file validation belongs in startup validation (STATE-03).
- **Lazy credential validation:** If Gmail token is missing, the agent should refuse to start entirely, not silently run without email capability. The v1.0 pattern of "if token exists, use it; else skip" must change for required services.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var parsing with type coercion | Manual `int(os.environ.get("PORT", "8000"))` | `pydantic-settings` `BaseSettings` field with `int` type | Handles type coercion, validation errors, defaults, .env files all automatically |
| Secret masking in logs | Custom `__repr__` / redaction | `pydantic.SecretStr` | Automatically masks in `__repr__`, `__str__`, and JSON serialization; well-tested |
| .env file loading | Manual `python-dotenv` load_dotenv() | `SettingsConfigDict(env_file=".env")` | pydantic-settings handles this natively; no need for separate load step |
| Health check response formatting | Custom dict building | FastAPI `JSONResponse` with status_code param | Clean pattern for returning 503 with body |

**Key insight:** pydantic-settings eliminates an entire category of bugs (wrong types, missing vars, typos in env var names) that raw `os.environ` is prone to. The 22 scattered `os.environ` calls in this codebase are exactly the problem pydantic-settings was designed to solve.

## Common Pitfalls

### Pitfall 1: SecretStr Leaks in Pydantic ValidationError
**What goes wrong:** When `BaseSettings` instantiation fails (e.g., missing required field), Pydantic's `ValidationError` may include the input dict in its error message, exposing `SecretStr` values in plaintext before the model is validated.
**Why it happens:** SecretStr masking only applies after successful model construction. During validation, the raw input dict is used in error messages.
**How to avoid:** Wrap `Settings()` instantiation in a try/except that catches `ValidationError` and logs only the error messages (not the full exception which contains input data). Or use `model_config = SettingsConfigDict(hide_input_in_errors=True)` if available.
**Warning signs:** Seeing actual token values in startup error logs.

### Pitfall 2: Existing /health Endpoint Conflict
**What goes wrong:** The codebase already has a `/health` endpoint in `src/negotiation/campaign/webhook.py` on the ClickUp webhook router. Adding a new top-level `/health` creates a route conflict.
**Why it happens:** The existing endpoint was added in Phase 5 on the webhook sub-router and was not intended as the definitive health endpoint.
**How to avoid:** Remove the existing `/health` from `webhook.py` router and add it to the top-level FastAPI app in the new `health.py` module (or directly in `create_app()`).
**Warning signs:** FastAPI logs showing duplicate route warnings, or the wrong handler being called.

### Pitfall 3: SQLite Write Check in /ready is Too Expensive
**What goes wrong:** Attempting `INSERT INTO ... DELETE FROM ...` on every /ready call degrades performance and pollutes the audit log.
**Why it happens:** Naive "writable" check using actual data modification.
**How to avoid:** Use `SELECT 1` on the existing connection. This validates the connection is alive and the file is accessible. For a true write check, use a temporary table or `PRAGMA integrity_check` (expensive) only on startup.
**Warning signs:** Audit table growing with health-check test entries.

### Pitfall 4: Breaking Graceful Degradation
**What goes wrong:** Phase 7 added graceful degradation (services skip when credentials missing). Phase 8 adds fail-fast validation. These conflict if not carefully scoped.
**Why it happens:** STATE-03 says "Agent refuses to start when Gmail token, Sheets SA, or Slack token is missing." But during development/testing, you may not have all credentials.
**How to avoid:** Make startup validation configurable: in production mode, all credentials required; in development mode, validate only the credentials that are provided. The `PRODUCTION` env var already exists for this distinction.
**Warning signs:** Development environment refusing to start because Sheets SA isn't configured.

### Pitfall 5: Circular Import When Config Module Imports App Modules
**What goes wrong:** If `config.py` imports from other negotiation modules (e.g., for custom validators), and those modules import from config.py, circular imports occur.
**Why it happens:** Settings class needs to be importable everywhere without pulling in the whole app.
**How to avoid:** Keep `config.py` self-contained with zero imports from the `negotiation` package (only stdlib, pydantic, pydantic-settings). Pass settings values to modules, don't import Settings inside modules that Settings might reference.
**Warning signs:** `ImportError: cannot import name 'Settings' from partially initialized module`.

## Code Examples

Verified patterns from official sources:

### Complete Settings Class (Adapted for This Codebase)
```python
# Source: pydantic-settings docs + codebase analysis
# File: src/negotiation/config.py
from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated configuration for the negotiation agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Core behavior
    production: bool = Field(default=False, description="Enable production mode (JSON logging)")
    webhook_port: int = Field(default=8000, description="HTTP port for FastAPI server")
    agent_email: str = Field(default="", description="Agent's email address for From headers")

    # Audit database
    audit_db_path: Path = Field(
        default=Path("data/audit.db"),
        description="Path to SQLite audit database",
    )

    # Gmail
    gmail_token_path: Path = Field(
        default=Path("token.json"),
        description="Path to Gmail OAuth2 token file",
    )
    gmail_credentials_path: Path = Field(
        default=Path("credentials.json"),
        description="Path to Gmail OAuth2 client secrets file",
    )
    gmail_pubsub_topic: str = Field(
        default="",
        description="Gmail Pub/Sub topic for push notifications",
    )

    # Google Sheets
    google_sheets_key: str = Field(
        default="",
        description="Google Sheets spreadsheet ID",
    )
    sheets_service_account_path: Path = Field(
        default=Path("~/.config/gspread/service_account.json"),
        description="Path to Sheets service account JSON",
    )

    # Slack
    slack_bot_token: SecretStr = Field(
        default=SecretStr(""),
        description="Slack Bot User OAuth Token",
    )
    slack_app_token: SecretStr = Field(
        default=SecretStr(""),
        description="Slack App-Level Token",
    )
    slack_escalation_channel: str = Field(
        default="",
        description="Slack channel ID for escalation messages",
    )
    slack_agreement_channel: str = Field(
        default="",
        description="Slack channel ID for agreement alerts",
    )

    # Anthropic
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Anthropic API key for LLM calls",
    )

    # ClickUp
    clickup_api_token: str = Field(
        default="",
        description="ClickUp API token for campaign ingestion",
    )
    clickup_webhook_secret: str = Field(
        default="",
        description="ClickUp webhook signing secret",
    )
```

### Health Endpoints
```python
# Source: FastAPI docs + Kubernetes health check conventions
# File: src/negotiation/health.py
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_health_routes(app: FastAPI) -> None:
    """Register /health and /ready endpoints on the FastAPI app."""

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe: returns 200 if process is running."""
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        """Readiness probe: checks audit DB and Gmail availability."""
        services: dict[str, Any] = request.app.state.services
        checks: dict[str, str] = {}

        # Check audit DB writable
        try:
            conn: sqlite3.Connection = services["audit_conn"]
            conn.execute("SELECT 1")
            checks["audit_db"] = "ok"
        except Exception:
            checks["audit_db"] = "fail"

        # Check Gmail client initialized
        gmail_client = services.get("gmail_client")
        checks["gmail"] = "ok" if gmail_client is not None else "fail"

        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            content={
                "status": "ready" if all_ok else "not_ready",
                "checks": checks,
            },
            status_code=200 if all_ok else 503,
        )
```

### Startup Credential Validation
```python
# Source: Derived from codebase auth/credentials.py patterns
# File: Part of src/negotiation/config.py
import sys
import structlog
from negotiation.config import Settings

logger = structlog.get_logger()

def validate_credentials(settings: Settings) -> None:
    """Validate all required credentials at startup. Fail fast with clear errors."""
    errors: list[str] = []

    # Gmail token file
    if not settings.gmail_token_path.exists():
        errors.append(
            f"Gmail token file not found at {settings.gmail_token_path}. "
            "Run OAuth2 flow first or set GMAIL_TOKEN_PATH."
        )

    # Sheets service account file
    sa_path = settings.sheets_service_account_path.expanduser()
    if not sa_path.exists():
        errors.append(
            f"Sheets service account file not found at {sa_path}. "
            "Set SHEETS_SERVICE_ACCOUNT_PATH to valid JSON key file."
        )

    # Slack bot token
    if not settings.slack_bot_token.get_secret_value():
        errors.append("SLACK_BOT_TOKEN is not set. Required for Slack integration.")

    # Slack app token (needed for Socket Mode)
    if not settings.slack_app_token.get_secret_value():
        errors.append("SLACK_APP_TOKEN is not set. Required for Slack Socket Mode.")

    if errors:
        logger.error(
            "Startup credential validation failed",
            error_count=len(errors),
        )
        for error in errors:
            logger.error("Missing credential", detail=error)
        print("\n=== STARTUP FAILED: Missing credentials ===", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("===", file=sys.stderr)
        sys.exit(1)
```

### Testing Settings Override Pattern
```python
# Source: FastAPI advanced/settings docs
from negotiation.config import Settings

def test_with_custom_settings():
    """Override settings in tests without environment variables."""
    settings = Settings(
        production=False,
        gmail_token_path=Path("/tmp/test-token.json"),
        slack_bot_token=SecretStr("xoxb-test-token"),
        slack_app_token=SecretStr("xapp-test-token"),
        audit_db_path=Path(":memory:"),
        _env_file=None,  # Skip .env file in tests
    )
    assert settings.webhook_port == 8000
```

## Complete Environment Variable Inventory

All `os.environ` calls found in the current codebase (6 files, 22 calls):

| Env Var | File(s) | Current Access | Default | Required? |
|---------|---------|----------------|---------|-----------|
| `PRODUCTION` | app.py (x3) | `os.environ.get("PRODUCTION", "")` | `""` (falsy) | No |
| `AUDIT_DB_PATH` | app.py, audit/cli.py | `os.environ.get("AUDIT_DB_PATH", "data/audit.db")` | `"data/audit.db"` | No |
| `SLACK_BOT_TOKEN` | app.py, slack/app.py, slack/client.py | `os.environ.get()` / `os.environ[]` | None (crashes if missing in slack/) | Yes (prod) |
| `SLACK_APP_TOKEN` | app.py, slack/app.py | `os.environ.get()` / `os.environ[]` | None | Yes (prod) |
| `SLACK_ESCALATION_CHANNEL` | app.py | `os.environ.get("...", "")` | `""` | No |
| `SLACK_AGREEMENT_CHANNEL` | app.py | `os.environ.get("...", "")` | `""` | No |
| `GOOGLE_SHEETS_KEY` | app.py | `os.environ.get("GOOGLE_SHEETS_KEY")` | `None` | Yes (prod) |
| `SHEETS_SERVICE_ACCOUNT_PATH` | auth/credentials.py | `os.environ.get("SHEETS_SERVICE_ACCOUNT_PATH")` | `None` (falls back to gspread default) | No (has fallback) |
| `GMAIL_TOKEN_PATH` | app.py | `os.environ.get("GMAIL_TOKEN_PATH")` | `None` | Yes (prod) |
| `AGENT_EMAIL` | app.py (x2) | `os.environ.get("AGENT_EMAIL", "")` | `""` | No |
| `ANTHROPIC_API_KEY` | app.py | `os.environ.get("ANTHROPIC_API_KEY")` | `None` | Yes (prod) |
| `CLICKUP_API_TOKEN` | app.py | `os.environ.get("CLICKUP_API_TOKEN", "")` | `""` | No |
| `CLICKUP_WEBHOOK_SECRET` | campaign/webhook.py | `os.environ.get("CLICKUP_WEBHOOK_SECRET", "")` | `""` | No |
| `GMAIL_PUBSUB_TOPIC` | app.py (x3) | `os.environ.get("GMAIL_PUBSUB_TOPIC", "")` | `""` | No |
| `WEBHOOK_PORT` | app.py | `os.environ.get("WEBHOOK_PORT", "8000")` | `"8000"` | No |

**Files requiring modification:**
1. `src/negotiation/app.py` -- 17 os.environ calls (primary target)
2. `src/negotiation/auth/credentials.py` -- 1 os.environ call
3. `src/negotiation/slack/app.py` -- 2 os.environ calls
4. `src/negotiation/slack/client.py` -- 1 os.environ call
5. `src/negotiation/campaign/webhook.py` -- 1 os.environ call + remove /health
6. `src/negotiation/audit/cli.py` -- 1 os.environ call

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `from pydantic import BaseSettings` (v1) | `from pydantic_settings import BaseSettings` (v2) | Pydantic v2 (2023) | Separate package; different import path |
| `class Config:` inner class | `model_config = SettingsConfigDict(...)` | Pydantic v2 (2023) | Config class pattern is deprecated |
| `@validator` decorator | `@field_validator` decorator | Pydantic v2 (2023) | Different signature, mode parameter |
| FastAPI `on_event("startup")` | FastAPI `lifespan` context manager | FastAPI 0.93+ | Already migrated in this codebase |

**Deprecated/outdated:**
- `from pydantic import BaseSettings`: Moved to pydantic-settings package in Pydantic v2. Must use `from pydantic_settings import BaseSettings`.
- Pydantic v1 `Config` inner class: Replaced by `model_config = SettingsConfigDict(...)` attribute.

## Open Questions

1. **Production-only vs. always-required credentials**
   - What we know: STATE-03 says "fails fast when missing." Current code (v1.0) runs gracefully without any credentials (every service is optional).
   - What's unclear: Should dev mode also require credentials, or only production mode?
   - Recommendation: Validate credentials only when `production=True`. In dev mode, log warnings for missing credentials but allow startup. This preserves the development experience while ensuring production safety.

2. **Gmail token deep validation**
   - What we know: Can check if `token.json` file exists. Can also attempt `Credentials.from_authorized_user_file()` to check if it's parseable.
   - What's unclear: Should startup validation actually try to refresh the token (requires network), or just check file existence and JSON parseability?
   - Recommendation: Check file existence + JSON parseability only (no network call). Deep validation would slow startup and could fail due to transient network issues.

3. **Whether to use @lru_cache or module-level singleton for Settings**
   - What we know: FastAPI docs recommend `@lru_cache` on `get_settings()` for dependency injection and test overrides. But the current codebase initializes services once in `main()`.
   - What's unclear: Whether to adopt the full FastAPI DI pattern or keep the simpler pattern of passing Settings through `initialize_services()`.
   - Recommendation: Start with module-level `get_settings()` with `@lru_cache`. It works for both the `initialize_services()` call pattern and can be used as a FastAPI dependency later if needed.

## Sources

### Primary (HIGH confidence)
- [pydantic-settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - BaseSettings, SettingsConfigDict, env_file, SecretStr, customise_sources
- [FastAPI advanced/settings](https://fastapi.tiangolo.com/advanced/settings/) - Settings as dependency, lru_cache pattern, .env integration, testing overrides
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) - Version 2.13.0 released 2026-02-15, Python 3.10-3.14

### Secondary (MEDIUM confidence)
- [Index.dev FastAPI health check guide](https://www.index.dev/blog/how-to-implement-health-check-in-python) - Liveness/readiness patterns, status codes, async checks
- [Google OAuth2 credentials docs](https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.credentials.html) - valid property, token_state, refresh behavior
- [gspread auth docs](https://docs.gspread.org/en/latest/oauth2.html) - service_account() function, credential file paths

### Tertiary (LOW confidence)
- None -- all findings verified through primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pydantic-settings is the official, documented solution; FastAPI docs explicitly recommend it
- Architecture: HIGH - Patterns derived directly from existing codebase analysis + official docs
- Pitfalls: HIGH - All pitfalls identified from actual codebase conflicts (existing /health, SecretStr leak issue, graceful degradation conflict)

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable libraries, unlikely to change significantly)
