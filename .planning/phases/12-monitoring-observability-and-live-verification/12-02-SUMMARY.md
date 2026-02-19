---
phase: 12-monitoring-observability-and-live-verification
plan: 02
subsystem: testing
tags: [pytest, live-tests, gmail, google-sheets, slack, integration-testing]

# Dependency graph
requires:
  - phase: 08-config-health
    provides: Settings class with centralized credential management
  - phase: 02-email-integration
    provides: GmailClient with send/receive/watch operations
  - phase: 03-sheets-integration
    provides: SheetsClient with get_all_influencers
  - phase: 04-slack-integration
    provides: SlackNotifier with chat_postMessage
provides:
  - "@pytest.mark.live marker infrastructure via pyproject.toml"
  - "Session-scoped fixtures for real Gmail, Sheets, and Slack clients"
  - "Live Gmail send/receive test"
  - "Live Sheets read test"
  - "Live Slack message delivery test"
affects: [ci-cd, deployment-verification]

# Tech tracking
tech-stack:
  added: []
  patterns: [pytest-marker-based-test-segmentation, session-scoped-live-fixtures, credential-skip-pattern]

key-files:
  created:
    - tests/live/__init__.py
    - tests/live/conftest.py
    - tests/live/test_gmail_live.py
    - tests/live/test_sheets_live.py
    - tests/live/test_slack_live.py
  modified:
    - pyproject.toml

key-decisions:
  - "Native pytest marker via pyproject.toml addopts -- no custom CLI options or collection hooks needed"
  - "Session-scoped fixtures to avoid re-creating API clients per test"
  - "Credential-skip pattern: each fixture pytest.skip() if creds unavailable, no hard failures"

patterns-established:
  - "Live test marker: @pytest.mark.live for all tests requiring real external service credentials"
  - "Default exclusion: addopts '-m not live' in pyproject.toml ensures CI never runs live tests"
  - "Override pattern: 'pytest -m live' overrides default addopts to select only live tests"
  - "Fixture-level skip: each fixture checks credential availability and skips gracefully"

requirements-completed: [CONFIG-02]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 12 Plan 02: Live Integration Tests Summary

**Opt-in live integration tests with @pytest.mark.live for Gmail send/receive, Sheets read, and Slack message delivery using real credentials**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T20:24:43Z
- **Completed:** 2026-02-19T20:27:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Registered @pytest.mark.live marker in pyproject.toml with default exclusion via addopts
- Created session-scoped fixtures for gmail_client, sheets_client, slack_notifier, and agent_email with graceful credential skipping
- Implemented 4 live tests: Gmail send (with response validation), Gmail watch setup, Sheets read, and Slack message post
- Verified 718 existing tests pass unaffected, 4 live tests correctly collected via `-m live`

## Task Commits

Each task was committed atomically:

1. **Task 1: Set up pytest live marker infrastructure and live test fixtures** - `bc58e04` (chore)
2. **Task 2: Write live integration tests for Gmail, Sheets, and Slack** - `7b2630c` (feat)

## Files Created/Modified
- `pyproject.toml` - Added live marker registration and `-m 'not live'` to addopts (already present from 12-01)
- `tests/live/__init__.py` - Package marker for live test directory
- `tests/live/conftest.py` - Session-scoped fixtures for real Gmail, Sheets, Slack clients with credential-skip pattern
- `tests/live/test_gmail_live.py` - Live Gmail send-to-self and watch setup tests
- `tests/live/test_sheets_live.py` - Live Sheets read test with empty-sheet error handling
- `tests/live/test_slack_live.py` - Live Slack message post test with `[LIVE TEST]` prefix

## Decisions Made
- **Native pytest marker approach:** Used pyproject.toml addopts and markers instead of custom pytest plugins or collection hooks. This is simpler, more standard, and requires zero additional code in conftest.py.
- **Session-scoped fixtures:** All live fixtures are session-scoped to avoid creating multiple API clients per test, reducing API calls and setup time.
- **Credential-skip pattern:** Each fixture checks for its required credentials and calls `pytest.skip()` if unavailable. This means live tests can be invoked safely even without all credentials -- only the tests with available credentials will run.

## Deviations from Plan

None - plan executed exactly as written.

Note: pyproject.toml already contained the marker registration and addopts changes from plan 12-01, so Task 1's pyproject.toml edit was effectively a no-op for that file.

## Out-of-scope Discovery

Pre-existing lint errors in `tests/test_metrics.py` (unused imports from plan 12-01) were logged to `deferred-items.md` and not addressed per scope boundary rules.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. Live tests use the same credentials already configured for the production agent.

## Next Phase Readiness
- Live test infrastructure complete and ready for use
- Plan 12-03 can proceed with any remaining phase 12 work
- All live tests can be run with `pytest -m live -v` once credentials are available

## Self-Check: PASSED

All 5 created files verified on disk. Both task commits (bc58e04, 7b2630c) verified in git log.

---
*Phase: 12-monitoring-observability-and-live-verification*
*Completed: 2026-02-19*
