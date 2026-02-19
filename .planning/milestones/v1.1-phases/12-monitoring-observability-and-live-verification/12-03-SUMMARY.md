---
phase: 12-monitoring-observability-and-live-verification
plan: 03
subsystem: infra
tags: [gmail, watch, sqlite, persistence, renewal, asyncio]

# Dependency graph
requires:
  - phase: 12-01
    provides: "Observability setup (metrics, sentry, middleware) and app.py structure with renew_gmail_watch_periodically"
provides:
  - "GmailWatchStore for persisting watch expiration to SQLite"
  - "Expiration-aware renewal loop (survives process restarts)"
  - "gmail_watch_state table with singleton row pattern"
  - "Configurable safety margin for watch renewal"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Singleton row pattern with CHECK (id = 1) for single-value SQLite tables"
    - "Expiration-aware async renewal loop reading persisted timestamps"

key-files:
  created:
    - src/negotiation/state/watch_store.py
    - tests/state/test_watch_store.py
  modified:
    - src/negotiation/state/schema.py
    - src/negotiation/config.py
    - src/negotiation/app.py

key-decisions:
  - "Singleton row pattern (CHECK id=1) instead of key-value table for watch state"
  - "Mocked datetime in tests to avoid sleep-based timestamp assertions"

patterns-established:
  - "Singleton row pattern: CHECK (id = 1) constraint for tables storing one row of state"

requirements-completed: [CONFIG-03]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 12 Plan 03: Gmail Watch Expiration Persistence Summary

**GmailWatchStore with SQLite singleton-row persistence and expiration-aware renewal loop replacing fixed 6-day timer**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T20:31:32Z
- **Completed:** 2026-02-19T20:34:45Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Replaced fixed 6-day Gmail watch renewal timer with expiration-aware loop that computes sleep from persisted timestamp
- Created GmailWatchStore with save/load for SQLite-backed expiration persistence using singleton row pattern
- Added configurable safety margin (gmail_watch_safety_margin_seconds, default 3600) for watch renewal timing
- Process restarts now read persisted expiration and renew immediately if expired

## Task Commits

Each task was committed atomically:

1. **Task 1: Create GmailWatchStore and update schema, config, and renewal logic** - `3095f40` (feat)
2. **Task 2: Add unit tests for GmailWatchStore and renewal logic** - `e473044` (test)

## Files Created/Modified
- `src/negotiation/state/watch_store.py` - GmailWatchStore class with save/load for expiration persistence
- `src/negotiation/state/schema.py` - Added init_gmail_watch_state_table with singleton row constraint
- `src/negotiation/config.py` - Added gmail_watch_safety_margin_seconds setting (default 3600)
- `src/negotiation/app.py` - Updated initialize_services, lifespan, and renew_gmail_watch_periodically
- `tests/state/test_watch_store.py` - 4 unit tests covering save/load, empty state, singleton, timestamps

## Decisions Made
- Singleton row pattern (CHECK id=1) instead of key-value table for watch state -- simpler upsert and no need for key management
- Mocked datetime in timestamp test to avoid unreliable sleep-based assertions at second granularity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_save_updates_updated_at timing issue**
- **Found during:** Task 2 (unit tests)
- **Issue:** Plan suggested brief sleep for timestamp change test, but timestamps at second granularity made 50ms sleep insufficient
- **Fix:** Used unittest.mock.patch to control datetime, asserting exact timestamp values
- **Files modified:** tests/state/test_watch_store.py
- **Verification:** All 4 tests pass reliably
- **Committed in:** e473044 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test reliability fix. No scope creep.

## Issues Encountered
None beyond the test timing fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 12 (final phase) is now complete with all 3 plans executed
- All observability, live verification, and persistence infrastructure in place
- 731 tests passing with zero failures across the full test suite

## Self-Check: PASSED

- All 5 files verified present on disk
- Commit 3095f40 (Task 1) verified in git log
- Commit e473044 (Task 2) verified in git log

---
*Phase: 12-monitoring-observability-and-live-verification*
*Completed: 2026-02-19*
