---
phase: 22-per-campaign-sheet-routing
plan: 02
subsystem: api
tags: [ingestion, google-sheets, campaign-routing, per-campaign-sheet]

# Dependency graph
requires:
  - phase: 22-01
    provides: Campaign model with influencer_sheet_tab/influencer_sheet_id fields and SheetsClient spreadsheet_key_override support
provides:
  - Ingestion pipeline wiring for per-campaign sheet tab and spreadsheet ID routing
  - find_influencer calls use campaign-specific worksheet_name and spreadsheet_key_override
affects: [negotiation-pipeline, campaign-ingestion]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-campaign-sheet-routing-in-ingestion]

key-files:
  created: []
  modified:
    - src/negotiation/campaign/ingestion.py
    - tests/campaign/test_ingestion.py

key-decisions:
  - "Empty string sheet routing fields normalized to None at build_campaign level"

patterns-established:
  - "Per-campaign sheet routing: worksheet_name defaults to Sheet1, spreadsheet_key_override defaults to None"

requirements-completed: [INGEST-03]

# Metrics
duration: 2min
completed: 2026-03-09
---

# Phase 22 Plan 02: Per-Campaign Sheet Routing in Ingestion Summary

**Ingestion pipeline wired to pass per-campaign sheet tab and spreadsheet ID to find_influencer, with 7 new routing tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-09T21:11:32Z
- **Completed:** 2026-03-09T21:14:02Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- build_campaign extracts influencer_sheet_tab and influencer_sheet_id from parsed ClickUp fields
- ingest_campaign passes per-campaign worksheet_name and spreadsheet_key_override to find_influencer
- Empty/whitespace-only sheet routing values normalized to None
- 7 new tests covering all routing scenarios (field population, defaults, empty strings, tab/id/default routing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire build_campaign to populate sheet routing fields** - `87d0007` (feat)
2. **Task 2: Add tests for per-campaign sheet routing in ingestion** - `c980dc8` (test)

## Files Created/Modified
- `src/negotiation/campaign/ingestion.py` - Added sheet routing field extraction in build_campaign and per-campaign routing in ingest_campaign
- `tests/campaign/test_ingestion.py` - Added TestPerCampaignSheetRouting class with 7 tests

## Decisions Made
- Empty string sheet routing fields are normalized to None at the build_campaign level (strip + falsy check)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed existing test side_effect functions for new keyword args**
- **Found during:** Task 2 (test verification)
- **Issue:** Existing `find_influencer_side_effect` functions in TestIngestCampaign did not accept the new `worksheet_name` and `spreadsheet_key_override` keyword args
- **Fix:** Added `**kwargs: Any` to both side_effect function signatures
- **Files modified:** tests/campaign/test_ingestion.py
- **Verification:** All 69 ingestion tests pass
- **Committed in:** c980dc8 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for backward compatibility of existing tests with new call signature. No scope creep.

## Issues Encountered

Pre-existing collection errors in tests/test_orchestration.py, tests/test_sentry.py, tests/email/ due to missing `mailparser_reply` module. Unrelated to this plan's changes -- out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Per-campaign sheet routing is fully wired end-to-end
- Campaigns with ClickUp sheet tab/ID custom fields will route to the correct spreadsheet and tab
- Campaigns without overrides default to master sheet, Sheet1 tab (backward compatible)

---
*Phase: 22-per-campaign-sheet-routing*
*Completed: 2026-03-09*
