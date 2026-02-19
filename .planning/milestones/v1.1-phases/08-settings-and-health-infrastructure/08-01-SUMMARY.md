---
phase: 08-settings-and-health-infrastructure
plan: 01
subsystem: infra
tags: [pydantic-settings, configuration, credential-validation, env-vars]

# Dependency graph
requires: []
provides:
  - "Centralized Settings class with typed fields for all 16 env vars"
  - "get_settings() cached accessor for test-friendly configuration"
  - "validate_credentials() startup gate for production mode"
  - "Zero os.environ calls in any src/negotiation/ module"
affects: [08-02, 09-settings-and-health-infrastructure]

# Tech tracking
tech-stack:
  added: [pydantic-settings, python-dotenv]
  patterns: [centralized-settings, fail-fast-startup, secret-str-for-tokens]

key-files:
  created:
    - src/negotiation/config.py
  modified:
    - pyproject.toml
    - src/negotiation/app.py
    - src/negotiation/auth/credentials.py
    - src/negotiation/slack/app.py
    - src/negotiation/slack/client.py
    - src/negotiation/campaign/webhook.py
    - src/negotiation/audit/cli.py
    - tests/test_app.py
    - tests/campaign/test_webhook.py
    - tests/auth/test_credentials.py

key-decisions:
  - "Settings stored on services dict and FastAPI app.state for endpoint access"
  - "Tests pass Settings objects directly instead of patching env vars"
  - "Slack/client functions require explicit tokens (no env fallback)"

patterns-established:
  - "Settings pattern: all env vars in src/negotiation/config.py Settings class"
  - "Credential validation: fail-fast in production, warn-only in dev"
  - "SecretStr for sensitive values: slack tokens, API keys never leak in logs"
  - "Test pattern: construct Settings explicitly for test isolation"

requirements-completed: [CONFIG-01, STATE-03]

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 8 Plan 1: Centralized Config Summary

**Pydantic-settings Settings class replacing 22 scattered os.environ calls with typed, validated, cached configuration and production credential gates**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-19T17:40:06Z
- **Completed:** 2026-02-19T17:47:58Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Created `src/negotiation/config.py` with Settings(BaseSettings) class mapping all 16 environment variables as typed fields with SecretStr for sensitive values
- Replaced all 22 os.environ calls across 6 source files with Settings-derived values
- Added validate_credentials() startup gate that exits with clear errors in production mode and logs warnings in dev mode
- Updated all tests to pass Settings objects directly, achieving full test isolation from env vars (691 tests passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config module with Settings class and credential validation** - `999ba7d` (feat)
2. **Task 2: Replace all os.environ calls with Settings across 6 source files** - `7aa431b` (refactor)

## Files Created/Modified
- `src/negotiation/config.py` - Settings class, get_settings(), validate_credentials()
- `pyproject.toml` - Added pydantic-settings>=2.13.0 dependency
- `src/negotiation/app.py` - Replaced 17 os.environ calls, added Settings parameter to initialize_services()
- `src/negotiation/auth/credentials.py` - Removed env var fallback in get_sheets_client()
- `src/negotiation/slack/app.py` - Removed env var fallbacks, require explicit tokens
- `src/negotiation/slack/client.py` - Removed env var fallback, require explicit bot_token
- `src/negotiation/campaign/webhook.py` - Read clickup_webhook_secret from app.state.settings
- `src/negotiation/audit/cli.py` - Replaced env var default with string literal
- `tests/test_app.py` - Rewritten to pass Settings objects directly
- `tests/campaign/test_webhook.py` - Updated to set settings on app.state
- `tests/auth/test_credentials.py` - Updated to remove env var fallback test

## Decisions Made
- Settings stored in both services dict (`_settings` key) and FastAPI `app.state.settings` for access from webhook endpoints
- Tests refactored to construct Settings objects explicitly rather than patching env vars -- this eliminates lru_cache interference between tests
- Slack Bolt app and SlackNotifier now require explicit tokens (ValueError if missing) instead of silently falling back to env vars

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_webhook.py for new Settings-based secret access**
- **Found during:** Task 2 (replacing os.environ in webhook.py)
- **Issue:** Webhook tests created a minimal FastAPI app without app.state.settings, causing AttributeError
- **Fix:** Set app.state.settings on test app, updated test_missing_webhook_secret to use Settings with empty secret
- **Files modified:** tests/campaign/test_webhook.py
- **Verification:** All webhook tests pass
- **Committed in:** 7aa431b (Task 2 commit)

**2. [Rule 1 - Bug] Updated test_app.py for Settings-based service initialization**
- **Found during:** Task 2 (refactoring initialize_services)
- **Issue:** Tests using monkeypatch.setenv were defeated by lru_cache on get_settings(); tests for configure_logging PRODUCTION env var fallback no longer valid
- **Fix:** Rewrote all TestInitializeServices tests to pass Settings objects directly; updated TestConfigureLogging to test production=True parameter
- **Files modified:** tests/test_app.py
- **Verification:** All 23 app tests pass
- **Committed in:** 7aa431b (Task 2 commit)

**3. [Rule 1 - Bug] Updated test_credentials.py for removed env var fallback**
- **Found during:** Task 2 (removing os.environ from credentials.py)
- **Issue:** test_env_var_path tested SHEETS_SERVICE_ACCOUNT_PATH env var fallback that was removed
- **Fix:** Replaced with test verifying no-argument call falls back to gspread default
- **Files modified:** tests/auth/test_credentials.py
- **Verification:** All credential tests pass
- **Committed in:** 7aa431b (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs -- test updates needed for changed interfaces)
**Impact on plan:** All auto-fixes necessary for test correctness after interface changes. No scope creep.

## Issues Encountered
None -- plan executed cleanly. All 691 tests pass.

## User Setup Required
None - no external service configuration required. Users can optionally create a `.env` file to set environment variables, but defaults work for development.

## Next Phase Readiness
- Settings infrastructure is complete, ready for health check endpoints (08-02)
- All modules import from config.py -- future env var additions go in one place
- validate_credentials() foundation ready for additional production checks

## Self-Check: PASSED

- FOUND: src/negotiation/config.py
- FOUND: .planning/phases/08-settings-and-health-infrastructure/08-01-SUMMARY.md
- FOUND: commit 999ba7d
- FOUND: commit 7aa431b

---
*Phase: 08-settings-and-health-infrastructure*
*Completed: 2026-02-19*
