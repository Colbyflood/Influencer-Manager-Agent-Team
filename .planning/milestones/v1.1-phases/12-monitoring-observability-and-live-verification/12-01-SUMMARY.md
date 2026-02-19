---
phase: 12-monitoring-observability-and-live-verification
plan: 01
subsystem: observability
tags: [prometheus, sentry, structlog, middleware, metrics, request-tracing]

# Dependency graph
requires:
  - phase: 08-configuration-and-health
    provides: Settings class and health endpoints for config extension and route exclusion
  - phase: 09-state-persistence
    provides: Negotiation state store and recovery loop for business metric instrumentation
provides:
  - Prometheus /metrics endpoint with HTTP and custom business gauges
  - Sentry SDK initialization with structlog-sentry bridge
  - Request ID middleware binding X-Request-ID to structlog contextvars
  - Settings fields sentry_dsn and enable_metrics
affects: [12-02, 12-03, deployment, docker-compose]

# Tech tracking
tech-stack:
  added: [prometheus-fastapi-instrumentator, sentry-sdk, structlog-sentry, prometheus-client]
  patterns: [conditional middleware wiring, no-op guard for optional services, contextvars-based request tracing]

key-files:
  created:
    - src/negotiation/observability/__init__.py
    - src/negotiation/observability/metrics.py
    - src/negotiation/observability/sentry.py
    - src/negotiation/observability/middleware.py
    - tests/test_metrics.py
    - tests/test_request_id.py
    - tests/test_sentry.py
  modified:
    - src/negotiation/config.py
    - src/negotiation/app.py
    - pyproject.toml

key-decisions:
  - "SentryProcessor placed after add_log_level and before TimeStamper in structlog chain for correct structured context forwarding"
  - "Business metrics updated at state transitions (not by DB polling) for real-time accuracy"
  - "RequestIdMiddleware added before instrumentator so request_id is available in all instrumented request logs"

patterns-established:
  - "No-op guard: init_sentry returns immediately when DSN is empty, safe to call unconditionally"
  - "Conditional middleware: setup_metrics only called when enable_metrics is True in Settings"
  - "Request tracing: X-Request-ID bound to structlog contextvars for per-request log correlation"

requirements-completed: [OBS-03, OBS-04, OBS-05]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 12 Plan 01: Observability Foundations Summary

**Prometheus metrics endpoint with custom business gauges, Sentry error reporting via structlog-sentry bridge, and X-Request-ID tracing middleware**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T20:24:42Z
- **Completed:** 2026-02-19T20:28:15Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Prometheus /metrics endpoint exposing http_request_duration_seconds, http_requests_total, negotiation_active_total gauge, and negotiation_deals_closed_total counter
- Sentry SDK with structlog-sentry bridge that is a safe no-op when sentry_dsn is empty
- Request ID middleware generating UUID4 or echoing client-supplied X-Request-ID, bound to structlog contextvars
- Business metrics instrumented at all state transition points (startup recovery, new negotiation, accept, reject)
- 9 new unit tests all passing, 727 total tests passing with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create observability modules and update config/dependencies** - `b3fa093` (feat)
2. **Task 2: Wire observability into app.py and add unit tests** - `35be1c0` (feat)

## Files Created/Modified
- `src/negotiation/observability/__init__.py` - Package docstring
- `src/negotiation/observability/metrics.py` - Prometheus instrumentator setup and ACTIVE_NEGOTIATIONS/DEALS_CLOSED custom metrics
- `src/negotiation/observability/sentry.py` - Sentry SDK init with structlog-sentry SentryProcessor bridge
- `src/negotiation/observability/middleware.py` - RequestIdMiddleware binding X-Request-ID to structlog contextvars
- `src/negotiation/config.py` - Added sentry_dsn and enable_metrics settings fields
- `src/negotiation/app.py` - Wired metrics, middleware, Sentry into configure_logging/create_app/main; instrumented business metrics at state transitions
- `pyproject.toml` - Added prometheus-fastapi-instrumentator, sentry-sdk, structlog-sentry dependencies
- `tests/test_metrics.py` - 4 tests: endpoint format, excluded handlers, gauge changes, counter increments
- `tests/test_request_id.py` - 2 tests: auto-generated UUID, client echo
- `tests/test_sentry.py` - 3 tests: no-op path, SDK init params, processor callable

## Decisions Made
- SentryProcessor placed after add_log_level and before TimeStamper in structlog chain (per research guidance -- SentryProcessor must receive structured dicts, not formatted strings)
- Business metrics updated at state transitions (not by DB polling) for real-time accuracy without scrape-time overhead
- RequestIdMiddleware added before instrumentator so request_id is available in all instrumented request logs
- Removed unused prometheus_client imports from test file to satisfy ruff linter

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused imports in test_metrics.py**
- **Found during:** Task 2 (unit tests)
- **Issue:** REGISTRY and CollectorRegistry imported but not used, causing ruff F401 lint failure
- **Fix:** Removed unused imports
- **Files modified:** tests/test_metrics.py
- **Verification:** `ruff check` passes clean
- **Committed in:** 35be1c0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor lint cleanup. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Sentry is disabled by default (empty sentry_dsn). Prometheus metrics are enabled by default. To enable Sentry, set the SENTRY_DSN environment variable.

## Next Phase Readiness
- Observability foundations in place for structured logging dashboard (plan 02) and live verification (plan 03)
- /metrics endpoint ready for Prometheus scraping in Docker Compose deployment
- Sentry ready to capture errors when DSN is configured in production

---
*Phase: 12-monitoring-observability-and-live-verification*
*Completed: 2026-02-19*
