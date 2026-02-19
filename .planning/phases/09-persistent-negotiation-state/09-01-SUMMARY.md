---
phase: 09-persistent-negotiation-state
plan: 01
subsystem: database
tags: [sqlite, serialization, state-persistence, decimal-precision, json]

# Dependency graph
requires:
  - phase: 04-negotiation-state-machine
    provides: NegotiationStateMachine with trigger/history/is_terminal
  - phase: 05-campaign-models
    provides: Campaign pydantic model and CampaignCPMTracker
provides:
  - NegotiationStateStore with save/load_active/delete for SQLite-backed crash recovery
  - init_negotiation_state_table DDL for negotiation_state table
  - serialize/deserialize helpers for context dicts and CPM trackers
  - NegotiationStateMachine.from_snapshot() classmethod for reconstruction from persisted state
  - CampaignCPMTracker.to_dict()/from_dict() for lossless Decimal serialization
affects: [09-02-wiring, crash-recovery, orchestration-restart]

# Tech tracking
tech-stack:
  added: []
  patterns: [INSERT-OR-REPLACE-with-COALESCE, Decimal-as-string-JSON, from-snapshot-reconstruction]

key-files:
  created:
    - src/negotiation/state/__init__.py
    - src/negotiation/state/schema.py
    - src/negotiation/state/store.py
    - src/negotiation/state/serializers.py
    - tests/state/__init__.py
    - tests/state/test_store.py
    - tests/state/test_serializers.py
  modified:
    - src/negotiation/state_machine/machine.py
    - src/negotiation/campaign/cpm_tracker.py

key-decisions:
  - "Decimal values serialized as strings in JSON to avoid precision loss (floats never used)"
  - "INSERT OR REPLACE with COALESCE subquery preserves original created_at on updates"
  - "load_active uses TERMINAL_STATES from transitions module for single source of truth on filtering"
  - "row_factory temporarily set to sqlite3.Row then restored to avoid side effects"

patterns-established:
  - "from_snapshot pattern: classmethods for reconstructing domain objects from persisted data"
  - "to_dict/from_dict pattern: symmetric serialization on domain classes for JSON round-trips"
  - "DecimalEncoder: custom JSON encoder that converts Decimal to str"

requirements-completed: [STATE-01, STATE-02]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 9 Plan 01: Persistent Negotiation State Summary

**SQLite-backed negotiation state store with lossless Decimal serialization, from_snapshot reconstruction, and full round-trip verified by 12 unit tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T18:16:12Z
- **Completed:** 2026-02-19T18:20:19Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Created src/negotiation/state/ package with schema, store, and serializers for SQLite-backed crash recovery
- Added NegotiationStateMachine.from_snapshot() for explicit reconstruction without replaying events
- Added CampaignCPMTracker.to_dict()/from_dict() with Decimal precision preserved as strings
- 12 unit tests covering all persistence contracts including terminal state filtering and created_at preservation
- Full 714-test suite passes with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create state persistence module** - `ee48c54` (feat)
2. **Task 2: Write unit tests** - `3a1e8d9` (test)

## Files Created/Modified
- `src/negotiation/state/__init__.py` - Package exports for store, schema, and serializer functions
- `src/negotiation/state/schema.py` - init_negotiation_state_table DDL with state index
- `src/negotiation/state/store.py` - NegotiationStateStore with save, load_active, delete methods
- `src/negotiation/state/serializers.py` - serialize/deserialize helpers with DecimalEncoder
- `src/negotiation/state_machine/machine.py` - Added from_snapshot classmethod
- `src/negotiation/campaign/cpm_tracker.py` - Added to_dict/from_dict with Decimal-safe serialization
- `tests/state/__init__.py` - Test package init
- `tests/state/test_store.py` - 5 tests for store save/load/delete/overwrite/idempotent
- `tests/state/test_serializers.py` - 7 tests for context, CPM tracker, and state machine round-trips

## Decisions Made
- Decimal values serialized as strings in JSON -- the negotiation loop already does `Decimal(str(value))` on the way back, so string is the correct contract
- INSERT OR REPLACE with COALESCE subquery to preserve original created_at on updates -- simpler than separate INSERT/UPDATE paths
- load_active uses TERMINAL_STATES from transitions module rather than hardcoding state values -- single source of truth
- row_factory temporarily swapped to sqlite3.Row then restored to avoid side effects on the shared connection

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lint issues in test_store.py**
- **Found during:** Task 2 (unit tests)
- **Issue:** Unused NegotiationState import and line over 100 chars
- **Fix:** Removed unused import, split long SQL string across two lines
- **Files modified:** tests/state/test_store.py
- **Verification:** ruff check passes clean
- **Committed in:** 3a1e8d9 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor lint cleanup. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- State persistence data layer complete, ready for 09-02 wiring into the orchestration loop
- NegotiationStateStore.save()/load_active() provide the crash-recovery primitives
- from_snapshot and to_dict/from_dict enable full reconstruction of in-flight negotiations

## Self-Check: PASSED

All 9 files verified present on disk. Both commits (ee48c54, 3a1e8d9) verified in git log.

---
*Phase: 09-persistent-negotiation-state*
*Completed: 2026-02-19*
