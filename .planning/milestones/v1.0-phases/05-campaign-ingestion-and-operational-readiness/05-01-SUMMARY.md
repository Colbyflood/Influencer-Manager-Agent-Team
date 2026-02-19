---
phase: 05-campaign-ingestion-and-operational-readiness
plan: 01
subsystem: campaign, audit, resilience
tags: [pydantic, sqlite, tenacity, structlog, cpm-tracker, audit-trail, wal-mode]

# Dependency graph
requires:
  - phase: 01-core-domain
    provides: Platform enum from domain/types.py, PayRange Decimal pattern from domain/models.py
provides:
  - Campaign, CampaignInfluencer, CampaignCPMRange Pydantic models
  - CampaignCPMTracker with engagement-quality-weighted flexibility
  - EventType StrEnum and AuditEntry model
  - SQLite audit store (init, insert, query) with WAL mode
  - resilient_api_call retry decorator with Slack error notification
  - ClickUp custom field mapping config (campaign_fields.yaml)
affects: [05-02, 05-03, 05-04]

# Tech tracking
tech-stack:
  added: [fastapi, uvicorn, tenacity, structlog, httpx]
  patterns: [engagement-quality-weighted CPM flexibility, SQLite WAL mode audit store, tenacity retry decorator factory, ClickUp field mapping YAML]

key-files:
  created:
    - src/negotiation/campaign/__init__.py
    - src/negotiation/campaign/models.py
    - src/negotiation/campaign/cpm_tracker.py
    - src/negotiation/audit/__init__.py
    - src/negotiation/audit/models.py
    - src/negotiation/audit/store.py
    - src/negotiation/resilience/__init__.py
    - src/negotiation/resilience/retry.py
    - config/campaign_fields.yaml
    - tests/campaign/test_models.py
    - tests/campaign/test_cpm_tracker.py
    - tests/audit/test_store.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Used Decimal('0') start value in sum() for running_average_cpm to satisfy mypy strict return type"
  - "Exclusive comparisons for engagement tiers: >5% high, >3% moderate (matches project pattern from 03-02)"
  - "Budget premium distributed across remaining influencers using savings * agreed_count / remaining_count"
  - "Module-level _notifier with configure_error_notifier() avoids circular import with SlackNotifier"
  - "SQLite audit store uses datetime.UTC (Python 3.12+) per ruff UP017"

patterns-established:
  - "CPM flexibility: engagement quality weighting with hard cap at 120% of target max"
  - "Audit store: WAL mode, parameterized queries only, JSON metadata serialization"
  - "Retry decorator factory: tenacity with configurable api_name for logging context"

requirements-completed: [DATA-01, DATA-03]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 5 Plan 1: Foundation Models Summary

**Campaign Pydantic models with engagement-quality CPM tracker, SQLite WAL-mode audit store, and tenacity retry decorator with Slack error notification**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T13:24:22Z
- **Completed:** 2026-02-19T13:29:56Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Campaign, CampaignInfluencer, CampaignCPMRange Pydantic models with Decimal precision and float rejection (follows PayRange pattern)
- CampaignCPMTracker with engagement-quality-weighted flexibility: high engagement (>5%) gets 15% premium, moderate (>3%) gets 8%, hard cap at 120% of target max
- SQLite audit store with WAL mode, 3 indexes (influencer, campaign, timestamp), parameterized queries, and flexible query filtering
- Tenacity-based resilient_api_call decorator: 3 attempts, exponential backoff with jitter, Slack error notification on exhaustion
- ClickUp custom field mapping YAML config for campaign ingestion
- 48 tests total (33 campaign + 15 audit) all passing, plus 563 total project tests with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and create campaign + audit models with CPM tracker** - `1d56d94` (feat)
2. **Task 2: Create SQLite audit store and resilience retry decorator** - `ecc5a1f` (feat)

## Files Created/Modified
- `src/negotiation/campaign/__init__.py` - Package exports for campaign models and CPM tracker
- `src/negotiation/campaign/models.py` - Campaign, CampaignInfluencer, CampaignCPMRange Pydantic models
- `src/negotiation/campaign/cpm_tracker.py` - CampaignCPMTracker with engagement-quality flexibility
- `src/negotiation/audit/__init__.py` - Package exports for audit models and store
- `src/negotiation/audit/models.py` - EventType StrEnum and AuditEntry model
- `src/negotiation/audit/store.py` - SQLite audit store with WAL mode, init/insert/query/close
- `src/negotiation/resilience/__init__.py` - Package exports for retry decorator
- `src/negotiation/resilience/retry.py` - resilient_api_call decorator factory with Slack notification
- `config/campaign_fields.yaml` - ClickUp custom field name to model field mapping
- `tests/campaign/test_models.py` - 18 tests for campaign model validation
- `tests/campaign/test_cpm_tracker.py` - 15 tests for CPM flexibility calculations
- `tests/audit/test_store.py` - 15 tests for audit store operations
- `pyproject.toml` - Added fastapi, uvicorn, tenacity, structlog, httpx dependencies
- `uv.lock` - Updated lockfile

## Decisions Made
- Used `Decimal("0")` start value in `sum()` for `running_average_cpm` to satisfy mypy strict return type (Decimal / int = Decimal, but sum default start 0 makes return type `Decimal | int`)
- Exclusive comparisons for engagement tiers: >5% high, >3% moderate -- matches project pattern from 03-02 intent classification
- Budget premium distributed proportionally: savings per agreement * agreed count / remaining influencer count
- Module-level `_notifier` with `configure_error_notifier()` function avoids circular import with SlackNotifier while enabling Slack error reporting
- Used `datetime.UTC` alias (Python 3.12+) instead of `timezone.utc` per ruff UP017 rule

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed __all__ sort order for ruff RUF022**
- **Found during:** Task 1 (campaign __init__.py)
- **Issue:** "CPMFlexibility" sorted after "Campaign*" entries but ruff requires isort-style sorting where uppercase matters
- **Fix:** Moved "CPMFlexibility" to first position in __all__ list
- **Files modified:** src/negotiation/campaign/__init__.py
- **Verification:** `ruff check` passes
- **Committed in:** 1d56d94 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed mypy Decimal sum() return type**
- **Found during:** Task 1 (cpm_tracker.py)
- **Issue:** `sum(generator)` returns `Decimal | int` because default start is 0; mypy rejects division result as `Decimal | float`
- **Fix:** Added `Decimal("0")` as sum start parameter
- **Files modified:** src/negotiation/campaign/cpm_tracker.py
- **Verification:** `mypy` passes with no errors
- **Committed in:** 1d56d94 (Task 1 commit)

**3. [Rule 1 - Bug] Fixed ruff UP017/UP035/RUF100 lint issues in Task 2 files**
- **Found during:** Task 2 (store.py, retry.py)
- **Issue:** Used `timezone.utc` instead of `datetime.UTC`, imported `Callable` from `typing` instead of `collections.abc`, unused noqa directive
- **Fix:** Updated imports and removed unnecessary type: ignore comments
- **Files modified:** src/negotiation/audit/store.py, src/negotiation/resilience/retry.py
- **Verification:** `ruff check` and `mypy` both pass
- **Committed in:** ecc5a1f (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All auto-fixes were standard lint/type compliance. No scope creep.

## Issues Encountered
None -- plan executed cleanly after lint fixes.

## User Setup Required
None for this plan -- campaign ingestion from ClickUp requires configuration in a later plan (05-02 or 05-03).

## Next Phase Readiness
- Campaign models ready for ClickUp webhook ingestion (Plan 05-02)
- Audit store ready for event logging across all negotiation flows (Plan 05-03)
- Resilience retry decorator ready to wrap ClickUp API calls (Plan 05-02)
- All 563 project tests passing with no regressions

---
## Self-Check: PASSED

All 12 created files verified on disk. Both task commits (1d56d94, ecc5a1f) verified in git log.

---
*Phase: 05-campaign-ingestion-and-operational-readiness*
*Completed: 2026-02-19*
