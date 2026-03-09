---
phase: 21-negotiation-controls
plan: 01
subsystem: api
tags: [fastapi, state-machine, negotiation, pydantic]

# Dependency graph
requires:
  - phase: 19-campaign-api
    provides: "negotiation_states in-memory store and campaign API router"
provides:
  - "PAUSED and STOPPED negotiation states with pause/resume/stop state machine methods"
  - "Control API endpoints: pause, resume, stop, stop-by-agency"
  - "Inbound email guard for paused/stopped negotiations"
affects: [21-02-PLAN, dashboard-controls]

# Tech tracking
tech-stack:
  added: []
  patterns: ["pre_pause_state storage for reversible pause", "helper function for thread lookup with campaign verification"]

key-files:
  created: []
  modified:
    - src/negotiation/domain/types.py
    - src/negotiation/state_machine/transitions.py
    - src/negotiation/state_machine/machine.py
    - src/negotiation/api/negotiations.py
    - src/negotiation/app.py

key-decisions:
  - "STOPPED is terminal (no further transitions), PAUSED is non-terminal (resumable)"
  - "Resume bypasses transition map by directly restoring pre_pause_state and recording history manually"
  - "Extracted _get_thread_entry helper to deduplicate campaign/thread lookup across control endpoints"

patterns-established:
  - "Control endpoints use 409 Conflict for invalid state transitions"
  - "Bulk operations return 200 with count=0 when no matches (not an error)"

requirements-completed: [API-03, CTRL-03]

# Metrics
duration: 4min
completed: 2026-03-09
---

# Phase 21 Plan 01: Backend State Machine Extensions and Control API Summary

**PAUSED/STOPPED states with pause/resume/stop state machine methods, four control API endpoints, and inbound email guard**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-09T02:41:01Z
- **Completed:** 2026-03-09T02:45:22Z
- **Tasks:** 2
- **Files modified:** 8 (5 source + 3 test)

## Accomplishments
- Extended NegotiationState enum with PAUSED and STOPPED values
- Added pause/resume/stop methods to NegotiationStateMachine with pre_pause_state tracking
- Created four control API endpoints (pause, resume, stop, stop-by-agency) with proper conflict detection
- Wired pause/stop guard into process_inbound_email to skip paused/stopped negotiations
- Updated all existing tests to account for new states, events, and transitions (221 tests passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend domain types, transitions, and state machine** - `05c11a9` (feat)
2. **Task 2: Create control API endpoints and wire pause guard** - `2c95349` (feat)

## Files Created/Modified
- `src/negotiation/domain/types.py` - Added PAUSED and STOPPED to NegotiationState enum
- `src/negotiation/state_machine/transitions.py` - Added PAUSE/RESUME/STOP events, 13 new transitions, STOPPED to TERMINAL_STATES
- `src/negotiation/state_machine/machine.py` - Added _pre_pause_state, pause(), resume(), stop() methods, updated from_snapshot
- `src/negotiation/api/negotiations.py` - Added ControlResponse, BulkStopRequest/Response models, four control endpoints, _get_thread_entry helper
- `src/negotiation/app.py` - Added pause/stop guard in process_inbound_email
- `tests/state_machine/test_machine.py` - Updated to derive valid transitions from TRANSITIONS map
- `tests/state_machine/test_transitions.py` - Updated event count, transition count, terminal state tests
- `tests/domain/test_types.py` - Updated NegotiationState member count and expected values

## Decisions Made
- STOPPED is terminal (no further transitions), PAUSED is non-terminal (resumable)
- Resume bypasses transition map by directly restoring pre_pause_state and recording history manually
- Extracted _get_thread_entry helper to deduplicate campaign/thread lookup across control endpoints

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing tests for new enum members and transitions**
- **Found during:** Task 2 (verification step)
- **Issue:** Existing tests had hardcoded counts for NegotiationState members (8), NegotiationEvent members (8), TRANSITIONS entries (13), and TERMINAL_STATES size (2) that broke with new additions
- **Fix:** Updated test_types.py (10 members), test_transitions.py (11 events, 26 transitions, 3 terminal states), test_machine.py (derived VALID_TRANSITIONS from TRANSITIONS map, imported TERMINAL_STATES)
- **Files modified:** tests/domain/test_types.py, tests/state_machine/test_transitions.py, tests/state_machine/test_machine.py
- **Verification:** 221 tests pass
- **Committed in:** 2c95349 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary test updates for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Control API endpoints ready for frontend integration (Phase 21-02)
- State machine extensions fully tested and backward compatible
- Email guard active for paused/stopped negotiations

---
*Phase: 21-negotiation-controls*
*Completed: 2026-03-09*
