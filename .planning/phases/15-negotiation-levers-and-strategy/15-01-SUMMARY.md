---
phase: 15-negotiation-levers-and-strategy
plan: 01
subsystem: negotiation
tags: [lever-engine, cpm, deterministic, pydantic, strenum]

requires:
  - phase: 13-campaign-structured-models
    provides: "DeliverableScenarios, UsageRights, BudgetConstraints, ProductLeverage models"
  - phase: 14-knowledge-base-rewrite
    provides: "Lever preference order decision [14-01]"
provides:
  - "LeverAction enum with 9 negotiation tactics (NEG-08 through NEG-15)"
  - "NegotiationLeverContext frozen model for negotiation state"
  - "LeverResult frozen model with action, rates, and lever_instructions"
  - "select_lever deterministic engine with 8-step priority"
  - "build_opening_context helper for NEG-08 opening position"
affects: [15-02, 15-03, negotiation-orchestrator, email-composer]

tech-stack:
  added: []
  patterns: ["deterministic lever priority chain with early return", "frozen Pydantic models for immutable negotiation state"]

key-files:
  created:
    - src/negotiation/levers/__init__.py
    - src/negotiation/levers/models.py
    - src/negotiation/levers/engine.py
    - tests/levers/__init__.py
    - tests/levers/test_lever_engine.py
  modified: []

key-decisions:
  - "Lever priority: floor > ceiling > deliverables > usage rights > product > syndication > CPM share > exit"
  - "build_opening_context uses budget_constraints.cpm_target for floor, falls back to cpm_range.min_cpm"
  - "Rate recalculation for deliverable trades keeps current rate (CPM is views-based, not deliverable-count-based)"

patterns-established:
  - "Early-return priority chain: each lever check returns immediately if applicable"
  - "Helper functions for usage rights comparison and formatting"

requirements-completed: [NEG-08, NEG-09, NEG-10, NEG-11, NEG-12, NEG-13, NEG-14, NEG-15]

duration: 4min
completed: 2026-03-08
---

# Phase 15 Plan 01: Lever Engine Summary

**Deterministic lever selection engine with 8-step priority chain covering NEG-08 through NEG-15, plus opening position helper**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-08T21:48:36Z
- **Completed:** 2026-03-08T21:52:06Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- LeverAction StrEnum with 9 actions mapping to all 8 NEG requirements
- Deterministic select_lever engine with strict priority ordering
- build_opening_context for NEG-08 opening at scenario_1 and CPM floor
- 15 comprehensive tests covering all lever paths and priority edge cases
- 840 total tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Define lever models and action types** - `331ae20` (feat)
2. **Task 2 RED: Failing tests for lever engine** - `484b82e` (test)
3. **Task 2 GREEN: Implement lever selection engine** - `a7f04a7` (feat)

## Files Created/Modified
- `src/negotiation/levers/models.py` - LeverAction, NegotiationLeverContext, LeverResult data models
- `src/negotiation/levers/engine.py` - select_lever deterministic priority chain and build_opening_context
- `src/negotiation/levers/__init__.py` - Package exports for all public APIs
- `tests/levers/test_lever_engine.py` - 15 tests covering all lever scenarios and priorities
- `tests/levers/__init__.py` - Test package init

## Decisions Made
- Lever priority order follows Phase 14 KB decision [14-01]: deliverable tiers > usage rights > product > CPM sharing, with floor/ceiling enforcement taking absolute priority
- build_opening_context prefers budget_constraints.cpm_target over cpm_range.min_cpm for CPM floor derivation
- Rate recalculation for deliverable trade-downs keeps current rate unchanged since CPM is views-based

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Lever engine ready for integration with negotiation orchestrator
- select_lever can be called from counter-offer flow to determine next tactic
- build_opening_context can be called from start_negotiations_for_campaign

## Self-Check: PASSED

All 5 files verified present. All 3 commit hashes verified in git log.

---
*Phase: 15-negotiation-levers-and-strategy*
*Completed: 2026-03-08*
