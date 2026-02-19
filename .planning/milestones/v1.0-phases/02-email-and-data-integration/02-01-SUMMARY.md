---
phase: 02-email-and-data-integration
plan: 01
subsystem: auth
tags: [google-api, oauth2, gmail, gspread, pydantic, credentials]

# Dependency graph
requires:
  - phase: 01-core-domain-and-pricing-engine
    provides: "Platform enum, PayRange model, domain types"
provides:
  - "Gmail OAuth2 credential management (get_gmail_credentials, get_gmail_service)"
  - "Sheets service account credential management (get_sheets_client)"
  - "Email Pydantic models (EmailThreadContext, InboundEmail, OutboundEmail)"
  - "Sheets Pydantic model (InfluencerRow with float coercion and PayRange bridge)"
  - "All Phase 2 external dependencies installed"
affects: [02-02, 02-03, 03-llm-pipeline]

# Tech tracking
tech-stack:
  added: [google-api-python-client, google-auth, google-auth-oauthlib, google-auth-httplib2, gspread, mail-parser-reply, google-cloud-pubsub, google-api-python-client-stubs]
  patterns: [google-oauth2-token-caching, service-account-auth, float-to-decimal-coercion, frozen-pydantic-models]

key-files:
  created:
    - src/negotiation/auth/__init__.py
    - src/negotiation/auth/credentials.py
    - src/negotiation/email/__init__.py
    - src/negotiation/email/models.py
    - src/negotiation/sheets/__init__.py
    - src/negotiation/sheets/models.py
    - tests/auth/test_credentials.py
    - tests/email/test_models.py
    - tests/sheets/test_models.py
  modified:
    - pyproject.toml
    - uv.lock
    - .gitignore

key-decisions:
  - "Added type: ignore[import-untyped] for google_auth_oauthlib (no py.typed marker) and type: ignore[no-untyped-call] for Credentials.from_authorized_user_file"
  - "InfluencerRow coerces float->str->Decimal to avoid PayRange float rejection while preserving displayed precision from Sheets"
  - "Credential file paths (credentials.json, token.json, service_account.json) excluded via .gitignore for security"

patterns-established:
  - "Google OAuth2 token caching: load from file, refresh if expired, run flow if missing, persist after"
  - "Float-to-Decimal coercion pattern: field_validator converts float->str before Decimal parsing for Sheets data"
  - "Domain bridge pattern: InfluencerRow.to_pay_range() converts external data model to internal domain model"

requirements-completed: [EMAIL-01, EMAIL-03, DATA-02]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 2 Plan 1: Dependencies, Auth, and Domain Models Summary

**Gmail OAuth2 + Sheets service account auth module with email and sheets Pydantic models, including float-to-Decimal coercion for Sheets data bridging to PayRange**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T00:50:17Z
- **Completed:** 2026-02-19T00:54:59Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- Installed all 7 runtime + 1 dev Phase 2 dependencies (google-api-python-client, google-auth, gspread, mail-parser-reply, etc.)
- Created auth module with Gmail OAuth2 credential caching/refresh and Sheets service account client
- Created frozen Pydantic models for email domain (EmailThreadContext, InboundEmail, OutboundEmail) and sheets domain (InfluencerRow)
- InfluencerRow coerces Sheets floats to Decimal and bridges to PayRange via to_pay_range()
- 50 new tests (277 total), ruff clean, mypy clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Phase 2 dependencies and update .gitignore** - `1d00689` (chore)
2. **Task 2: Create auth module, email models, sheets models, and tests** - `98b1904` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `pyproject.toml` - Added 7 runtime + 1 dev dependency
- `uv.lock` - Lock file updated with all transitive dependencies
- `.gitignore` - Added credential file exclusions (credentials.json, token.json, service_account.json)
- `src/negotiation/auth/__init__.py` - Re-exports get_gmail_credentials, get_gmail_service, get_sheets_client
- `src/negotiation/auth/credentials.py` - Gmail OAuth2 and Sheets service account credential management
- `src/negotiation/email/__init__.py` - Re-exports EmailThreadContext, InboundEmail, OutboundEmail
- `src/negotiation/email/models.py` - Frozen Pydantic models for email domain
- `src/negotiation/sheets/__init__.py` - Re-exports InfluencerRow
- `src/negotiation/sheets/models.py` - InfluencerRow with float coercion and PayRange bridge
- `tests/auth/test_credentials.py` - 13 tests for credential management (mocked Google APIs)
- `tests/email/test_models.py` - 18 tests for email model validation and immutability
- `tests/sheets/test_models.py` - 19 tests for float coercion, validation, and PayRange bridging

## Decisions Made
- Added `type: ignore[import-untyped]` for google_auth_oauthlib and `type: ignore[no-untyped-call]` for Credentials.from_authorized_user_file -- these libraries lack py.typed markers
- InfluencerRow uses float->str->Decimal coercion (not direct float->Decimal) to preserve the displayed precision from Sheets while avoiding PayRange's float rejection validator
- Credential files excluded via .gitignore to prevent accidental secret commits

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused imports and import ordering in credentials.py and test files**
- **Found during:** Task 2 (post-implementation linting)
- **Issue:** Unused `json` import in credentials.py, unused `mock_open` and `pytest` imports in test_credentials.py, import blocks not sorted per isort rules
- **Fix:** Removed unused imports, ran ruff --fix for import sorting
- **Files modified:** src/negotiation/auth/credentials.py, tests/auth/test_credentials.py, tests/email/test_models.py
- **Verification:** `uv run ruff check src/ tests/` -- All checks passed
- **Committed in:** 98b1904 (part of Task 2 commit)

**2. [Rule 1 - Bug] Fixed mypy type: ignore comments**
- **Found during:** Task 2 (post-implementation type checking)
- **Issue:** Three `type: ignore` comments were unnecessary/wrong-code, missing `type: ignore[import-untyped]` for google_auth_oauthlib and `type: ignore[no-untyped-call]` for from_authorized_user_file
- **Fix:** Removed unused type: ignore comments, added correct ones for untyped third-party code
- **Files modified:** src/negotiation/auth/credentials.py
- **Verification:** `uv run mypy src/` -- Success: no issues found in 18 source files
- **Committed in:** 98b1904 (part of Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes were lint/type-check corrections. No scope creep.

## Issues Encountered
- Pre-existing formatting issues in src/negotiation/domain/errors.py and src/negotiation/domain/types.py (from Phase 1) -- out of scope, not fixed

## User Setup Required

**External services require manual configuration** before Gmail and Sheets integrations can be used at runtime:
- **Gmail API:** Enable in GCP Console, create OAuth2 Desktop client, configure consent screen with gmail.send and gmail.readonly scopes
- **Google Sheets API:** Enable in GCP Console, create service account, share spreadsheet with service account email
- **Environment variables:** GMAIL_CREDENTIALS_PATH (optional), GMAIL_TOKEN_PATH (optional), SHEETS_SERVICE_ACCOUNT_PATH (optional)
- **Credential files:** Place credentials.json and service_account.json in project root or configure paths via env vars

## Next Phase Readiness
- Auth module ready for Plans 02-02 (email service) and 02-03 (sheets service) to build upon
- Email and sheets models ready for service layer implementation
- All Phase 2 dependencies installed and importable

## Self-Check: PASSED

All 12 created files verified present. Both task commits (1d00689, 98b1904) verified in git history.

---
*Phase: 02-email-and-data-integration*
*Completed: 2026-02-19*
