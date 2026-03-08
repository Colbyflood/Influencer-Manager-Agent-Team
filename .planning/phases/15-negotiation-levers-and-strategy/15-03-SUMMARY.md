---
phase: 15-negotiation-levers-and-strategy
plan: 03
subsystem: negotiation
tags: [lever-engine, opening-context, campaign-data, negotiation-context, NEG-08]

requires:
  - phase: 15-negotiation-levers-and-strategy
    provides: "build_opening_context helper and select_lever engine from Plans 01-02"
  - phase: 13-campaign-structured-models
    provides: "DeliverableScenarios, UsageRights, BudgetConstraints, ProductLeverage models"
provides:
  - "Campaign sub-models (deliverables, usage_rights, budget_constraints, product_leverage) flow into negotiation context"
  - "Lever state defaults (current_scenario, usage_tier, booleans) initialized in context"
  - "Lever-driven initial outreach using build_opening_context for NEG-08 opening position"
affects: [negotiation-loop, email-composer, lever-engine-runtime]

tech-stack:
  added: []
  patterns: ["campaign sub-model passthrough via context dict", "lever engine opening position for initial outreach"]

key-files:
  created: []
  modified:
    - src/negotiation/app.py
    - tests/test_app.py
    - tests/test_orchestration.py

key-decisions:
  - "Campaign sub-models passed as direct references (not serialized) in context dict for lever engine consumption"
  - "Lever state defaults represent opening position: scenario=1, usage_tier=target, all booleans False"
  - "build_opening_context replaces calculate_initial_offer for lever-driven initial outreach"

patterns-established:
  - "Context dict carries both pricing data and lever state for the negotiation loop"
  - "lever_instructions parameter passed to compose_counter_email for NEG-08 opening guidance"

requirements-completed: [NEG-08, NEG-12]

duration: 3min
completed: 2026-03-08
---

# Phase 15 Plan 03: Campaign Context Wiring Summary

**Campaign sub-models flow through negotiation context with lever-driven initial outreach using build_opening_context for NEG-08 opening position**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T21:59:49Z
- **Completed:** 2026-03-08T22:03:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- build_negotiation_context returns all 4 campaign sub-models (deliverables, usage_rights, budget_constraints, product_leverage) plus 5 lever state defaults
- start_negotiations_for_campaign uses build_opening_context for opening rate (CPM floor) and deliverables (scenario_1)
- Initial outreach includes lever_instructions for NEG-08 opening guidance
- 3 new integration tests verify campaign data flows through context builder
- 846 total tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Pass campaign lever data through build_negotiation_context** - `d3fb5e8` (feat)
2. **Task 2: Use build_opening_context for initial outreach and add integration tests** - `f5fd0ff` (feat)

## Files Created/Modified
- `src/negotiation/app.py` - Added campaign sub-models and lever state defaults to context builder; replaced calculate_initial_offer with build_opening_context
- `tests/test_app.py` - 3 new tests for lever data in build_negotiation_context (full sub-models, None sub-models, backward compat)
- `tests/test_orchestration.py` - Updated expected context keys to include new lever data

## Decisions Made
- Campaign sub-models passed as direct object references in context dict (not serialized) so lever engine can access Pydantic model attributes directly
- Lever state defaults (scenario=1, usage_tier="target", all booleans False) represent the opening negotiation position
- build_opening_context replaces calculate_initial_offer, providing lever-driven rate and deliverables for initial outreach

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_orchestration expected keys for context dict**
- **Found during:** Task 2
- **Issue:** test_assembles_correct_keys in test_orchestration.py checked exact key set, failed with new lever keys
- **Fix:** Added 9 new lever keys to expected_keys set
- **Files modified:** tests/test_orchestration.py
- **Verification:** All 846 tests pass
- **Committed in:** f5fd0ff (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test compatibility. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- End-to-end lever integration complete: engine -> loop -> context -> outreach
- All campaign data flows through negotiation pipeline for lever-driven tactics
- Phase 15 complete -- lever engine fully wired into negotiation system

## Self-Check: PASSED

All 3 modified files verified present. Both commit hashes verified in git log.

---
*Phase: 15-negotiation-levers-and-strategy*
*Completed: 2026-03-08*
