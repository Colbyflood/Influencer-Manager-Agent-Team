---
phase: 22-per-campaign-sheet-routing
plan: 01
subsystem: api
tags: [pydantic, gspread, google-sheets, campaign-model]

# Dependency graph
requires: []
provides:
  - Campaign model with influencer_sheet_tab and influencer_sheet_id fields
  - ClickUp field mapping for sheet routing fields
  - SheetsClient with spreadsheet_key_override support
affects: [22-02, campaign-ingestion, negotiation-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [spreadsheet-key-override-param-pattern]

key-files:
  created: []
  modified:
    - src/negotiation/campaign/models.py
    - config/campaign_fields.yaml
    - src/negotiation/sheets/client.py
    - tests/sheets/test_client.py

key-decisions:
  - "Override spreadsheets opened without caching to support multiple campaigns with different sheets"
  - "Sheet routing fields are plain text in ClickUp, no special type parsing needed"

patterns-established:
  - "spreadsheet_key_override: optional param pattern for per-campaign sheet routing"

requirements-completed: [SHEET-01, SHEET-02, SHEET-03, INGEST-01, INGEST-02]

# Metrics
duration: 2min
completed: 2026-03-09
---

# Phase 22 Plan 01: Per-Campaign Sheet Routing Foundation Summary

**Campaign model with influencer_sheet_tab/influencer_sheet_id fields and SheetsClient spreadsheet_key_override for per-campaign sheet routing**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-09T21:07:39Z
- **Completed:** 2026-03-09T21:09:28Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added influencer_sheet_tab and influencer_sheet_id optional fields to Campaign model
- Mapped ClickUp form fields to model fields in campaign_fields.yaml
- Extended SheetsClient with spreadsheet_key_override param on all 3 public methods
- Added 3 new tests for override behavior (override, default, no-cache)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sheet fields to Campaign model and ClickUp config** - `5faeadd` (feat)
2. **Task 2: Extend SheetsClient with spreadsheet_key_override** - `e235b55` (feat)

## Files Created/Modified
- `src/negotiation/campaign/models.py` - Added influencer_sheet_tab and influencer_sheet_id optional fields
- `config/campaign_fields.yaml` - Added ClickUp field mapping for sheet routing fields
- `src/negotiation/sheets/client.py` - Added _get_spreadsheet_for() helper and spreadsheet_key_override param
- `tests/sheets/test_client.py` - Added TestSpreadsheetKeyOverride with 3 tests

## Decisions Made
- Override spreadsheets are opened without caching (each call opens fresh) since different campaigns may use different sheets
- Sheet routing fields are plain text in ClickUp -- no entries needed in field_types

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failure in tests/test_orchestration.py::TestBuildNegotiationContext::test_assembles_correct_keys (extra keys agency_name, counterparty_type). Unrelated to this plan's changes -- out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Campaign model and SheetsClient ready for plan 02 to wire routing logic
- Per-campaign sheet tab and spreadsheet ID can be populated from ClickUp form

---
*Phase: 22-per-campaign-sheet-routing*
*Completed: 2026-03-09*
