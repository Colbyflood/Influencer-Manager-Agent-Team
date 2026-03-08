---
phase: 13-campaign-data-model-expansion
plan: 03
subsystem: api
tags: [pricing, cpm, decimal, campaign-aware, boundaries]

requires:
  - phase: 13-campaign-data-model-expansion
    plan: 01
    provides: "BudgetConstraints sub-model with cpm_target and cpm_leniency_pct fields"
provides:
  - "derive_cpm_bounds() function for dynamic CPM floor/ceiling from campaign target + leniency"
  - "Campaign-aware CampaignCPMTracker instantiation using derived bounds"
  - "Campaign-aware initial offer calculation using derived CPM floor"
affects: [15-negotiation-levers]

tech-stack:
  added: []
  patterns: ["Campaign-derived CPM bounds replacing hardcoded defaults with backward-compatible fallback"]

key-files:
  created: []
  modified:
    - src/negotiation/pricing/engine.py
    - src/negotiation/app.py
    - tests/pricing/test_engine.py
    - tests/pricing/test_boundaries.py
    - tests/test_orchestration.py

key-decisions:
  - "derive_cpm_bounds returns CPM_FLOOR/CPM_CEILING defaults when campaign has no budget_constraints (backward compat)"
  - "Leniency defaults to 0% when cpm_target is provided but cpm_leniency_pct is None (ceiling = target)"

patterns-established:
  - "Campaign-derived bounds: use derive_cpm_bounds() to get floor/ceiling from campaign data before passing to pricing functions"

requirements-completed: [CAMP-08, CAMP-02, CAMP-05]

duration: 3min
completed: 2026-03-08
---

# Phase 13 Plan 03: Campaign-Aware CPM Pricing Summary

**Dynamic CPM floor/ceiling derived from per-campaign target + leniency percentage, replacing hardcoded $20-$30 range with backward-compatible fallback**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T21:06:01Z
- **Completed:** 2026-03-08T21:09:06Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added derive_cpm_bounds() to engine.py that converts CPM target + leniency into dynamic floor/ceiling
- Wired campaign-derived bounds into app.py for initial offer, CampaignCPMTracker, and negotiation context
- Added 11 new tests (7 for derive_cpm_bounds, 4 for campaign-aware boundary evaluation)
- All 784 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add campaign-aware CPM calculation helpers and update app.py wiring** - `9bb9d1d` (feat)
2. **Task 2: Add tests for campaign-aware CPM bounds and boundary evaluation** - `dfce05b` (test)

## Files Created/Modified
- `src/negotiation/pricing/engine.py` - Added derive_cpm_bounds() for dynamic CPM floor/ceiling
- `src/negotiation/app.py` - Wired campaign-derived bounds to pricing engine and CampaignCPMTracker
- `tests/pricing/test_engine.py` - Added TestDeriveCpmBounds with 7 test cases
- `tests/pricing/test_boundaries.py` - Added TestCampaignAwareBoundaries with 4 test cases
- `tests/test_orchestration.py` - Updated mock campaign helper and CPM-related tests

## Decisions Made
- derive_cpm_bounds returns CPM_FLOOR/CPM_CEILING defaults when campaign has no budget_constraints -- maintains full backward compatibility
- Leniency defaults to 0% when cpm_target is provided but cpm_leniency_pct is None -- ceiling equals target, meaning no room above target

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed orchestration test mocks for campaign-aware CPM bounds**
- **Found during:** Task 1 (after wiring app.py changes)
- **Issue:** Existing orchestration tests used MagicMock for campaign.budget_constraints, causing derive_cpm_bounds to receive MagicMock objects instead of Decimal/None
- **Fix:** Updated _make_mock_campaign to set budget_constraints=None by default, added cpm_target/cpm_leniency_pct parameters, updated test assertions
- **Files modified:** tests/test_orchestration.py
- **Verification:** All 15 orchestration tests pass
- **Committed in:** f636892

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test correctness after behavior change. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Campaign-aware CPM bounds ready for Phase 15 (negotiation levers) to use per-campaign pricing ranges
- Backward compatibility preserved: campaigns without budget_constraints fall back to $20/$30 defaults
- All 784 tests pass (no regressions)

---
*Phase: 13-campaign-data-model-expansion*
*Completed: 2026-03-08*
