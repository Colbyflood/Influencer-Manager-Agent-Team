---
phase: 05-campaign-ingestion-and-operational-readiness
plan: 02
subsystem: campaign, webhook, ingestion
tags: [fastapi, hmac, clickup, webhook, httpx, yaml, campaign-ingestion]

# Dependency graph
requires:
  - phase: 05-campaign-ingestion-and-operational-readiness
    provides: Campaign/CampaignInfluencer/CampaignCPMRange models, resilient_api_call decorator, campaign_fields.yaml config
  - phase: 02-email-and-data
    provides: SheetsClient with find_influencer lookup
  - phase: 04-slack-and-hitl
    provides: SlackNotifier with post_escalation for team notifications
provides:
  - FastAPI webhook endpoint with HMAC-SHA256 signature verification at /webhooks/clickup
  - Campaign ingestion pipeline (fetch task, parse fields, lookup influencers, Slack alerts)
  - set_campaign_processor callback registration for loose coupling
  - Configurable ClickUp field mapping via YAML
affects: [05-03, 05-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [HMAC-SHA256 webhook verification on raw bytes, pluggable callback for loose coupling, type-aware ClickUp custom field casting, contextlib.suppress for clean error handling]

key-files:
  created:
    - src/negotiation/campaign/webhook.py
    - src/negotiation/campaign/ingestion.py
    - tests/campaign/test_webhook.py
    - tests/campaign/test_ingestion.py
  modified:
    - src/negotiation/campaign/__init__.py

key-decisions:
  - "Pluggable callback pattern (set_campaign_processor) instead of direct import to avoid circular dependency and enable independent testing"
  - "structlog event_type kwarg instead of event to avoid conflict with structlog reserved keyword"
  - "contextlib.suppress for ClickUp number casting per ruff SIM105"
  - "Ternary operator for separator selection per ruff SIM108"

patterns-established:
  - "Webhook verification: always verify HMAC against raw body bytes BEFORE JSON parsing"
  - "ClickUp integration: always GET full task after webhook (payload may lack custom fields)"
  - "Module-level callback with setter function for loose coupling between webhook and processing"

requirements-completed: [DATA-01]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 5 Plan 2: ClickUp Webhook and Campaign Ingestion Summary

**FastAPI webhook endpoint with HMAC-SHA256 verification and campaign ingestion pipeline bridging ClickUp form data to negotiation system via Google Sheet lookup and Slack notifications**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T13:32:44Z
- **Completed:** 2026-02-19T13:38:37Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- FastAPI webhook endpoint at /webhooks/clickup verifying HMAC-SHA256 signatures against raw body bytes before JSON parsing (per research pitfall 4)
- Campaign ingestion pipeline: fetches full ClickUp task via API (per pitfall 1), parses custom fields with type-aware casting (per pitfall 3), builds Campaign model, looks up influencers in Google Sheet
- Missing influencers trigger individual Slack alerts asking team to add them (per locked decision: skip and notify)
- Team receives Slack notification when campaign ingestion starts with found/missing influencer counts
- 35 new tests (13 webhook + 22 ingestion) plus 630 total project tests passing with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: ClickUp webhook endpoint with HMAC signature verification** - `3ad99e9` (feat)
2. **Task 2: Campaign ingestion pipeline bridging ClickUp data to negotiation system** - `c0292ad` (feat)

## Files Created/Modified
- `src/negotiation/campaign/webhook.py` - FastAPI endpoint with HMAC verification, pluggable campaign processor callback, health check
- `src/negotiation/campaign/ingestion.py` - Full ingestion pipeline: load_field_mapping, fetch_clickup_task, parse_custom_fields, parse_influencer_list, build_campaign, ingest_campaign
- `src/negotiation/campaign/__init__.py` - Updated exports with all new public symbols alphabetically sorted
- `tests/campaign/test_webhook.py` - 13 tests covering signature verification, event filtering, callback dispatch, error handling
- `tests/campaign/test_ingestion.py` - 22 tests covering YAML loading, field parsing, influencer list splitting, campaign building, full integration with mocked services

## Decisions Made
- Used pluggable callback pattern (`set_campaign_processor`) instead of direct import of ingestion module in webhook -- avoids circular dependency and enables independent testing of the webhook layer without the ingestion module existing
- Used `event_type` keyword argument in structlog call instead of `event` to avoid conflict with structlog's reserved `event` keyword (first positional arg)
- Used `contextlib.suppress(ValueError)` for ClickUp number string casting per ruff SIM105 (replace try/except/pass)
- Used ternary operator for separator selection per ruff SIM108

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Refactored webhook to use pluggable callback pattern**
- **Found during:** Task 1
- **Issue:** Plan specified `from negotiation.campaign.ingestion import ingest_campaign` at function level, but ingestion module doesn't exist yet (Task 2). Tests fail with ModuleNotFoundError.
- **Fix:** Introduced `set_campaign_processor()` callback registration pattern -- webhook calls the registered callback instead of directly importing ingestion. This is a cleaner architecture and enables independent testability.
- **Files modified:** src/negotiation/campaign/webhook.py, tests/campaign/test_webhook.py
- **Verification:** All 13 webhook tests pass independently without ingestion module
- **Committed in:** 3ad99e9 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed structlog reserved keyword conflict**
- **Found during:** Task 1
- **Issue:** `logger.info("...", event=event)` fails because `event` is structlog's reserved first positional argument name
- **Fix:** Changed keyword to `event_type=event`
- **Files modified:** src/negotiation/campaign/webhook.py
- **Verification:** Test passes, structlog logs correctly
- **Committed in:** 3ad99e9 (Task 1 commit)

**3. [Rule 1 - Bug] Fixed ruff RUF100 unused noqa directive**
- **Found during:** Task 1
- **Issue:** `# noqa: PLW0603` on global statement but PLW0603 is not enabled in project config
- **Fix:** Removed unused noqa directive
- **Files modified:** src/negotiation/campaign/webhook.py
- **Verification:** `ruff check` passes
- **Committed in:** 3ad99e9 (Task 1 commit)

**4. [Rule 1 - Bug] Fixed ruff SIM105, SIM108, E501 in ingestion module**
- **Found during:** Task 2
- **Issue:** try/except/pass should use contextlib.suppress, if/else should use ternary, line too long
- **Fix:** Applied all three ruff suggestions
- **Files modified:** src/negotiation/campaign/ingestion.py
- **Verification:** `ruff check` passes
- **Committed in:** c0292ad (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (1 Rule 3 blocking, 3 Rule 1 bugs)
**Impact on plan:** Rule 3 fix improved architecture (callback pattern is cleaner than function-level import). Rule 1 fixes are standard lint compliance. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
ClickUp webhook configuration requires:
- `CLICKUP_WEBHOOK_SECRET` environment variable (returned when webhook is created via ClickUp API)
- `CLICKUP_API_TOKEN` environment variable (from ClickUp Settings -> Apps -> API Token)

## Next Phase Readiness
- Webhook endpoint ready to receive ClickUp form submissions
- Ingestion pipeline ready to fetch task data, parse custom fields, and look up influencers
- Campaign processor callback ready to be wired into the app startup (Plan 04)
- All 630 project tests passing with no regressions

---
## Self-Check: PASSED
