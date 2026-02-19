---
phase: 05-campaign-ingestion-and-operational-readiness
plan: 04
subsystem: app
tags: [fastapi, slack-bolt, structlog, asyncio, uvicorn, audit-wiring, socket-mode]

# Dependency graph
requires:
  - phase: 05-02
    provides: "ClickUp webhook endpoint and campaign ingestion pipeline"
  - phase: 05-03
    provides: "Audit trail logger, store, CLI, and Slack /audit command"
provides:
  - "Application entry point combining FastAPI + Slack Bolt concurrently"
  - "Audit wiring module connecting logger to negotiation pipeline"
  - "Structlog configuration with JSON (prod) and console (dev) modes"
  - "Service initialization with graceful degradation for missing credentials"
affects: []

# Tech tracking
tech-stack:
  added: [structlog-dual-mode, uvicorn-async, asyncio-gather]
  patterns: [wrapper-pattern-for-audit, graceful-service-degradation, background-task-tracking]

key-files:
  created:
    - src/negotiation/app.py
    - src/negotiation/audit/wiring.py
    - tests/test_app.py
    - tests/audit/test_wiring.py
  modified:
    - src/negotiation/audit/__init__.py

key-decisions:
  - "Used logging.INFO/DEBUG integers instead of structlog.get_level_from_name (not available in structlog 25.5.0)"
  - "Removed structlog.stdlib.add_logger_name processor since PrintLoggerFactory lacks .name attribute"
  - "Local imports for SlackNotifier and SheetsClient inside initialize_services for graceful degradation"
  - "Background task set pattern to prevent GC of asyncio.ensure_future results (per RUF006)"

patterns-established:
  - "Wrapper pattern: create_audited_* functions wrap originals with logging without modifying source"
  - "Graceful service degradation: missing env vars skip service init instead of failing"
  - "Background task tracking: set + done_callback.discard to prevent garbage collection"

requirements-completed: [DATA-01, DATA-03, DATA-04]

# Metrics
duration: 6min
completed: 2026-02-19
---

# Phase 5 Plan 4: App Entry Point and Audit Wiring Summary

**Production-ready entry point combining FastAPI webhooks + Slack Bolt Socket Mode with audit logging wired into all pipeline operations via structlog**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-19T13:41:44Z
- **Completed:** 2026-02-19T13:48:37Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Audit wiring module with 5 wrapper functions connecting AuditLogger to email send/receive, negotiation loop, campaign ingestion, and SlackDispatcher -- all without modifying original source code
- Application entry point running FastAPI (port 8000 for ClickUp webhooks) and Slack Bolt (Socket Mode for /audit, /claim, /resume) concurrently via asyncio.gather
- Structlog dual-mode configuration: JSON rendering at INFO for production, colored console at DEBUG for development
- Service initialization with graceful degradation when SLACK_BOT_TOKEN, GOOGLE_SHEETS_KEY, or other credentials are missing
- Full test suite: 661 tests pass (31 new) with zero regressions across all 5 phases

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit wiring module** - `1000520` (feat)
2. **Task 2: Application entry point** - `1c46c2d` (feat)

## Files Created/Modified
- `src/negotiation/audit/wiring.py` - Wrapper functions adding audit logging to pipeline operations
- `src/negotiation/app.py` - Application entry point combining FastAPI + Slack Bolt + structlog
- `src/negotiation/audit/__init__.py` - Updated exports with wiring functions
- `tests/audit/test_wiring.py` - 17 tests covering all wrappers and passthrough behavior
- `tests/test_app.py` - 14 tests for logging config, service init, and app creation

## Decisions Made
- Used `logging.INFO`/`logging.DEBUG` integer levels for `make_filtering_bound_logger` since `structlog.get_level_from_name` does not exist in structlog 25.5.0
- Removed `structlog.stdlib.add_logger_name` from processor chain since `PrintLoggerFactory` creates loggers without a `.name` attribute
- SlackNotifier and SheetsClient imported locally inside `initialize_services` to enable graceful degradation when credentials are missing (no import-time failures)
- Used background task set with `done_callback.discard` to prevent asyncio task garbage collection per ruff RUF006

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed structlog.get_level_from_name not available**
- **Found during:** Task 2 (Application entry point)
- **Issue:** `structlog.get_level_from_name` does not exist in structlog 25.5.0
- **Fix:** Used `logging.INFO`/`logging.DEBUG` integer constants directly with `make_filtering_bound_logger`
- **Files modified:** src/negotiation/app.py
- **Verification:** All structlog tests pass, logging works in both modes
- **Committed in:** 1c46c2d (Task 2 commit)

**2. [Rule 1 - Bug] Fixed PrintLogger missing .name attribute**
- **Found during:** Task 2 (Application entry point)
- **Issue:** `structlog.stdlib.add_logger_name` requires a stdlib logger with `.name`, but `PrintLoggerFactory` creates `PrintLogger` without it
- **Fix:** Removed `add_logger_name` from processor chain
- **Files modified:** src/negotiation/app.py
- **Verification:** All 661 tests pass, no AttributeError
- **Committed in:** 1c46c2d (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for structlog compatibility with the installed version. No scope creep.

## Issues Encountered
- FastAPI `on_event("startup")`/`on_event("shutdown")` triggers deprecation warning recommending lifespan handlers. Left as-is since it works correctly and is non-blocking for v1.

## User Setup Required
None - no external service configuration required beyond existing environment variables.

## Next Phase Readiness
- All 5 phases complete -- the system is production-ready
- Application starts with `python -m negotiation.app` (or gracefully reports missing credentials)
- Every email sent/received in the negotiation loop is automatically audit-logged
- Campaign ingestion from ClickUp webhook triggers negotiation start with audit logging
- All external API calls have retry logic (3x backoff, then Slack #errors)
- Full test suite: 661 tests across all phases pass with zero regressions

## Self-Check: PASSED

All files verified present, all commits verified in git log.

---
*Phase: 05-campaign-ingestion-and-operational-readiness*
*Completed: 2026-02-19*
