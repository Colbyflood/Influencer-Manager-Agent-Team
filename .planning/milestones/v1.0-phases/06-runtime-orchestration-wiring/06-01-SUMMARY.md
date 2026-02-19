---
phase: 06-runtime-orchestration-wiring
plan: 01
subsystem: api
tags: [fastapi, gmail, pubsub, asyncio, slack, lifespan, webhooks]

# Dependency graph
requires:
  - phase: 05-campaign-ingestion-and-operational-readiness
    provides: "App entry point with initialize_services, audit wiring, campaign webhook"
  - phase: 02-email-and-data
    provides: "GmailClient with send, receive, and watch operations"
  - phase: 04-slack-and-hitl
    provides: "SlackDispatcher, ThreadStateManager, triggers config"
  - phase: 03-llm-pipeline
    provides: "process_influencer_reply negotiation loop, Anthropic client"
provides:
  - "Full runtime orchestration with lifespan context manager"
  - "Gmail Pub/Sub push notification endpoint at POST /webhooks/gmail"
  - "Inbound email processing pipeline: get_message -> pre_check -> process_influencer_reply -> handle_result -> send_reply"
  - "GmailClient, Anthropic client, SlackDispatcher initialization in initialize_services"
  - "Gmail watch registration on startup and periodic renewal every 6 days"
  - "In-memory negotiation state store with history ID lock"
  - "webhook.py converted to APIRouter pattern"
affects: [06-02, 06-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FastAPI lifespan context manager replacing deprecated on_event"
    - "asyncio.to_thread for all synchronous Google API calls in async contexts"
    - "asyncio.Lock for thread-safe history ID updates"
    - "APIRouter composition pattern for webhook routes"
    - "Background task set with done_callback.discard for asyncio task GC prevention"

key-files:
  created: []
  modified:
    - "src/negotiation/app.py"
    - "src/negotiation/campaign/webhook.py"
    - "src/negotiation/campaign/__init__.py"
    - "tests/campaign/test_webhook.py"

key-decisions:
  - "Tasks 1 and 2 committed together since both modify app.py and are interdependent"
  - "ThreadStateManager created before Bolt app block so SlackDispatcher can use it independently"
  - "In-memory negotiation state dict keyed by thread_id (acknowledged v1 restart limitation)"
  - "Pass proposed_cpm=0.0 and intent_confidence=1.0 to pre_check since values unknown before classification"
  - "Gmail watch renewed every 6 days via asyncio.sleep background task (expires at 7 days)"

patterns-established:
  - "Lifespan context manager: co-locates startup (Gmail watch) and shutdown (audit DB close) in a single async generator"
  - "Service initialization graceful degradation: try/except with None fallback for GmailClient, Anthropic, SlackDispatcher"
  - "APIRouter composition: webhook routes defined as Router, included in app via include_router"

requirements-completed: []

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 6 Plan 01: Runtime Orchestration Wiring Summary

**FastAPI lifespan with Gmail Pub/Sub webhook, inbound email pipeline wiring GmailClient -> SlackDispatcher -> process_influencer_reply -> send_reply, and APIRouter composition**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T15:22:37Z
- **Completed:** 2026-02-19T15:26:34Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Replaced deprecated FastAPI on_event handlers with lifespan context manager
- Added GmailClient, Anthropic client, and SlackDispatcher initialization to initialize_services with graceful degradation
- Created POST /webhooks/gmail endpoint that receives Pub/Sub push notifications and triggers the full negotiation pipeline
- Wired complete inbound email flow: fetch_new_messages -> get_message -> pre_check -> process_influencer_reply -> handle_negotiation_result -> send_reply
- Added Gmail watch registration on startup and periodic renewal every 6 days
- Protected history ID updates with asyncio.Lock to prevent race conditions
- Converted webhook.py from standalone FastAPI app to APIRouter pattern
- All 661 existing tests continue to pass

## Task Commits

Both tasks were implemented in a single atomic commit since they modify the same file (app.py) with interdependent changes:

1. **Task 1+2: Router conversion, lifespan, service init, Gmail webhook, inbound pipeline** - `8dde992` (feat)

**Plan metadata:** [pending] (docs: complete plan)

## Files Created/Modified
- `src/negotiation/app.py` - Full runtime orchestration: lifespan, initialize_services extended with GmailClient/Anthropic/SlackDispatcher/negotiation_states, Gmail Pub/Sub endpoint, process_inbound_email pipeline, watch renewal task
- `src/negotiation/campaign/webhook.py` - Converted from FastAPI app to APIRouter
- `src/negotiation/campaign/__init__.py` - Updated exports from app to router
- `tests/campaign/test_webhook.py` - Updated to use router wrapped in minimal FastAPI app for TestClient

## Decisions Made
- **Tasks combined into single commit:** Both tasks modify app.py and are interdependent (gmail_notification endpoint calls process_inbound_email, lifespan calls setup_watch). Separating into two commits would require an intermediate broken state.
- **ThreadStateManager moved before Bolt app block:** Previously created inside `if bolt_app is not None` block, now created unconditionally so SlackDispatcher can use it regardless of Bolt availability.
- **In-memory negotiation state:** Using dict keyed by thread_id. Acknowledged v1 limitation -- state lost on restart.
- **Pre-check CPM/confidence defaults:** Pass 0.0/1.0 since values are unknown before classification. Only human takeover and human reply detection gates fire at pre-check stage.
- **Audit wiring order:** wire_audit_to_dispatcher and create_audited_process_reply called during service initialization, before any requests are processed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated campaign __init__.py exports**
- **Found during:** Task 1 (Router conversion)
- **Issue:** `src/negotiation/campaign/__init__.py` re-exported `app` from webhook.py, causing ImportError after renaming to `router`
- **Fix:** Changed import and `__all__` to use `router` instead of `app`
- **Files modified:** `src/negotiation/campaign/__init__.py`
- **Verification:** All imports and tests pass
- **Committed in:** 8dde992 (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for import chain. No scope creep.

## Issues Encountered
None - plan executed cleanly after fixing the __init__.py export.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Runtime orchestration wired: inbound emails trigger the full negotiation pipeline
- Ready for Plan 06-02 (campaign-to-negotiation handoff) to wire ingestion results into negotiation state creation
- Ready for Plan 06-03 (integration testing) to verify end-to-end flows

## Self-Check: PASSED

All files exist, all commits verified, SUMMARY.md created.

---
*Phase: 06-runtime-orchestration-wiring*
*Completed: 2026-02-19*
