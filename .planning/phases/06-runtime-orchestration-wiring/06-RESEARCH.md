# Phase 6: Runtime Orchestration Wiring - Research

**Researched:** 2026-02-19
**Domain:** FastAPI application wiring, asyncio orchestration, Gmail Pub/Sub integration
**Confidence:** HIGH

## Summary

Phase 6 is a pure orchestration phase. All 22 v1 requirements are implemented and tested at the component level (661 tests). The milestone audit identified 4 critical gaps (MISSING-01 through MISSING-04) plus 4 tech debt items, all localized to `src/negotiation/app.py` (303 lines). No new libraries are needed -- every dependency already exists in pyproject.toml.

The work is connecting existing, tested components in the runtime entry point. The key challenge is not building new functionality but correctly composing async tasks (Gmail polling, FastAPI routes, Slack Socket Mode) into the existing `asyncio.gather` pattern and ensuring graceful degradation when credentials are missing.

**Primary recommendation:** Modify `app.py` to wire GmailClient, SlackDispatcher, process_influencer_reply, and campaign-to-negotiation handoff. Replace deprecated `on_event` with lifespan context manager. Add a `/webhooks/gmail` Pub/Sub push endpoint and a periodic watch renewal task.

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| FastAPI | >=0.129.0 | HTTP server for webhooks | Installed, in use |
| uvicorn | >=0.41.0 | ASGI server | Installed, in use |
| anthropic | >=0.82.0 | LLM client for intent/composition | Installed, used by negotiation_loop |
| google-api-python-client | >=2.190.0 | Gmail API service | Installed, used by GmailClient |
| google-cloud-pubsub | >=2.35.0 | Pub/Sub (already a dependency) | Installed, NOT YET USED |
| slack-bolt | >=1.27.0 | Slack Socket Mode + commands | Installed, in use |
| structlog | >=25.5.0 | Structured logging | Installed, in use |
| tenacity | >=9.1.4 | Retry with backoff | Installed, in use |

### Supporting (Already Installed)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| gspread | >=6.2.1 | Google Sheets access | Installed, in use |
| pydantic | >=2.12 | Data models | Installed, in use |
| httpx | >=0.28.1 | Async HTTP client | Installed, used by ClickUp fetch |

### No New Dependencies Needed
All libraries required for wiring are already in `pyproject.toml`. The `google-cloud-pubsub` package is already listed but has no runtime usage yet (it was added in anticipation of Gmail push notifications).

## Architecture Patterns

### Current app.py Structure (303 lines)
```
app.py
  configure_logging()          -- structlog setup
  initialize_services()        -- creates audit DB, SlackNotifier, SheetsClient, Bolt app, wires campaign processor
  create_app(services)         -- returns FastAPI app with on_event handlers (DEPRECATED)
  run_slack_bot(services)      -- runs Bolt Socket Mode in asyncio.to_thread
  main()                       -- asyncio.gather(uvicorn.serve(), run_slack_bot())
```

### Target app.py Structure After Phase 6
```
app.py
  configure_logging()          -- unchanged
  initialize_services()        -- EXTENDED: add GmailClient, SlackDispatcher, Anthropic client, CampaignCPMTracker
  lifespan(app)                -- NEW: replaces on_event; calls setup_watch, schedules watch renewal
  create_app(services)         -- MODIFIED: uses lifespan, adds /webhooks/gmail route
  run_slack_bot(services)      -- unchanged
  handle_gmail_notification()  -- NEW: FastAPI route for Pub/Sub push
  process_inbound_email()      -- NEW: async function wiring GmailClient -> pre_check -> process_influencer_reply -> handle_result -> send reply
  start_negotiations()         -- NEW: async function consuming found_influencers from ingestion
  renew_gmail_watch()          -- NEW: periodic task to renew watch every 6 days
  main()                       -- EXTENDED: asyncio.gather adds watch renewal task
```

### Pattern 1: FastAPI Lifespan Context Manager (Replaces Deprecated on_event)
**What:** Replace `@app.on_event("startup")` / `@app.on_event("shutdown")` with a single `@asynccontextmanager` lifespan function.
**When to use:** Always for FastAPI apps on version >= 0.95.0.
**Why:** FastAPI deprecated `on_event` in favor of lifespan. The lifespan pattern co-locates startup and shutdown logic, making resource management clearer.

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup
    services = app.state.services
    audit_conn = services.get("audit_conn")
    gmail_client = services.get("gmail_client")
    if gmail_client:
        topic = os.environ.get("GMAIL_PUBSUB_TOPIC", "")
        if topic:
            watch_result = gmail_client.setup_watch(topic)
            services["history_id"] = watch_result.get("historyId", "")
            logger.info("Gmail watch registered", history_id=services["history_id"])
    logger.info("FastAPI application starting")
    yield
    # Shutdown
    if audit_conn is not None:
        close_audit_db(audit_conn)
        logger.info("Audit database connection closed")

app = FastAPI(title="Negotiation Agent Webhooks", lifespan=lifespan)
```

### Pattern 2: Gmail Pub/Sub Push Notification Webhook
**What:** A FastAPI POST endpoint that receives Google Pub/Sub push notifications when new emails arrive.
**When to use:** When Gmail `users.watch()` is configured with a push subscription pointing to this endpoint.

```python
# Source: https://developers.google.com/workspace/gmail/api/guides/push
import base64
import json
from fastapi import Request

@app.post("/webhooks/gmail")
async def gmail_notification(request: Request) -> dict[str, str]:
    """Handle Gmail Pub/Sub push notification."""
    body = await request.json()
    message_data = body.get("message", {}).get("data", "")
    decoded = json.loads(base64.urlsafe_b64decode(message_data))
    # decoded = {"emailAddress": "user@example.com", "historyId": "123456"}
    history_id = decoded.get("historyId", "")

    # Fetch new messages since last known history ID
    # Process each through the negotiation pipeline
    # Return 200 to acknowledge
    return {"status": "ok"}
```

### Pattern 3: Inbound Email Processing Pipeline
**What:** The full flow from receiving a Gmail notification to acting on it.
**Flow:**
1. Gmail Pub/Sub notification arrives with `historyId`
2. `GmailClient.fetch_new_messages(last_history_id)` returns new message IDs
3. For each message ID, `GmailClient.get_message(msg_id)` returns `InboundEmail`
4. `SlackDispatcher.pre_check()` runs gate checks (human takeover, human reply detection, trigger evaluation)
5. If pre_check returns None (proceed), call `process_influencer_reply()` with negotiation context
6. `SlackDispatcher.handle_negotiation_result()` dispatches Slack notifications
7. If action is "send", use `GmailClient.send_reply()` to send the counter-offer

### Pattern 4: Campaign Ingestion to Negotiation Handoff
**What:** After `ingest_campaign` returns `found_influencers`, start negotiations for each one.
**Flow for each found influencer:**
1. Extract `sheet_data` (InfluencerRow) from the found_influencers list
2. Call `sheets_client.get_pay_range(name)` to get the PayRange
3. Use `calculate_initial_offer(average_views)` to compute the first offer
4. Create `NegotiationStateMachine()` for the influencer
5. Compose initial outreach email using campaign context + influencer data
6. Send via `GmailClient.send()` as a new thread
7. Store negotiation state (state machine, thread_id, round_count) for later processing

### Pattern 5: Graceful Degradation (Existing Pattern, Must Preserve)
**What:** Services initialize with try/except and None fallbacks when credentials are missing.
**Critical rule:** Gmail, Slack, and Sheets clients can all be None. The app MUST start even without credentials, disabling features that require them.

```python
# Existing pattern from app.py line 106-123 -- follow this exactly for new services
gmail_client = None
gmail_token = os.environ.get("GMAIL_TOKEN_PATH")
if gmail_token:
    try:
        from negotiation.auth.credentials import get_gmail_service
        from negotiation.email.client import GmailClient
        service = get_gmail_service()
        agent_email = os.environ.get("AGENT_EMAIL", "")
        gmail_client = GmailClient(service, agent_email)
        logger.info("GmailClient initialized")
    except Exception:
        logger.warning("Failed to initialize GmailClient", exc_info=True)
else:
    logger.info("GMAIL_TOKEN_PATH not set, GmailClient disabled")
services["gmail_client"] = gmail_client
```

### Pattern 6: Background Task Tracking (Existing Pattern)
**What:** Background asyncio tasks are stored in a `set[asyncio.Task]` with `done_callback.discard` to prevent GC.
**Source:** Already implemented in app.py lines 176-193. Must reuse this pattern for new background tasks.

```python
# Existing pattern -- reuse for email processing and watch renewal tasks
background_tasks: set[asyncio.Task[Any]] = set()
task = asyncio.ensure_future(process_inbound_email(...))
background_tasks.add(task)
task.add_done_callback(background_tasks.discard)
```

### Anti-Patterns to Avoid
- **Synchronous Gmail calls in async handlers:** GmailClient methods are synchronous (they use the Google API client which is not async). MUST wrap in `asyncio.to_thread()` or `loop.run_in_executor()`.
- **Storing negotiation state only in memory:** State machines and round counts must persist somewhere. For v1, in-memory dict keyed by thread_id is acceptable (acknowledged limitation), but must document it as a restart-loses-state trade-off.
- **Direct import coupling between webhook and email processing:** Follow the existing `set_campaign_processor` callback pattern for loose coupling.
- **Blocking the event loop with Gmail API calls:** All Google API client calls are blocking I/O. Must use `asyncio.to_thread()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gmail push notifications | Custom polling loop | Gmail Pub/Sub push + `/webhooks/gmail` endpoint | Already have `google-cloud-pubsub` dependency; push is more efficient than polling; GmailClient.setup_watch() already implemented |
| Watch renewal scheduling | Custom timer/cron | `asyncio.sleep()` loop in a background task | Simple, no new dependencies; watch expires every 7 days, renew every 6 |
| Retry on API failure | Custom retry logic | `@resilient_api_call` decorator (already exists) | Already built with tenacity, Slack error notification on failure |
| State machine per negotiation | Custom state tracking | `NegotiationStateMachine` (already exists) | Validates transitions, records history, prevents invalid states |
| Escalation/agreement dispatch | Custom Slack posting | `SlackDispatcher.handle_negotiation_result()` (already exists) | Handles payload building, Block Kit formatting, routing |
| Audit logging | Manual log calls | `wire_audit_to_*` wrappers (already exist) | `create_audited_process_reply`, `wire_audit_to_dispatcher` already implemented and tested |

**Key insight:** Phase 6 should NOT create new classes or modules. All functionality exists. The work is calling existing functions from app.py in the right order with the right arguments.

## Common Pitfalls

### Pitfall 1: Blocking the Async Event Loop with Google API Calls
**What goes wrong:** `GmailClient.send()`, `fetch_new_messages()`, `get_message()`, `setup_watch()` are all synchronous (they use `googleapiclient` which is synchronous). Calling them directly in async handlers blocks the event loop, freezing uvicorn and Slack Socket Mode.
**Why it happens:** The Google API Python client does not support asyncio natively.
**How to avoid:** Wrap ALL GmailClient calls in `asyncio.to_thread()`:
```python
new_ids, new_history = await asyncio.to_thread(
    gmail_client.fetch_new_messages, last_history_id
)
```
**Warning signs:** Webhook responses taking 5+ seconds; Slack bot becoming unresponsive.

### Pitfall 2: Missing Negotiation Context for process_influencer_reply
**What goes wrong:** `process_influencer_reply` requires a `negotiation_context` dict with specific keys: `influencer_name`, `thread_id`, `platform`, `average_views`, `deliverables_summary`, `deliverable_types`, `next_cpm`, and optionally `history`. Missing keys cause KeyError or incorrect behavior.
**Why it happens:** The context must be built from multiple sources (Sheet data, campaign data, previous round state).
**How to avoid:** Build a helper function that assembles the context dict from InfluencerRow + Campaign + NegotiationStateMachine state.
**Warning signs:** KeyError in production logs from process_influencer_reply.

### Pitfall 3: Gmail History ID Tracking
**What goes wrong:** Each Pub/Sub notification includes a `historyId`. If you always use the ID from the watch response, you'll miss messages or re-process old ones. The history ID must be updated after each fetch.
**Why it happens:** `fetch_new_messages` returns `(message_ids, new_history_id)` -- the second return value must replace the stored one.
**How to avoid:** Store the latest history ID and update it after every successful `fetch_new_messages` call.
**Warning signs:** Duplicate email processing; missed emails after restart.

### Pitfall 4: Race Condition on Concurrent Pub/Sub Notifications
**What goes wrong:** Multiple Pub/Sub notifications can arrive rapidly. If two handlers run `fetch_new_messages` with the same `history_id`, they get the same messages and process them twice.
**Why it happens:** Pub/Sub delivers notifications at-least-once and can batch.
**How to avoid:** Use an `asyncio.Lock` around the history ID update + fetch operation. Or use a set of processed message IDs for deduplication.
**Warning signs:** Duplicate Slack notifications; duplicate reply emails sent.

### Pitfall 5: In-Memory State Loss on Restart
**What goes wrong:** If negotiation state machines and round counts are stored in-memory dicts, a process restart loses all active negotiations. The agent then cannot resume conversations.
**Why it happens:** v1 does not have a persistent negotiation state store.
**How to avoid:** This is an acknowledged v1 limitation. Document it. For production resilience, the audit trail can be used to reconstruct state, but that is v2 work. For now, use in-memory storage and accept the trade-off.
**Warning signs:** After deployment, agent sends initial offers to influencers already mid-negotiation.

### Pitfall 6: SlackDispatcher.pre_check Requires Gmail Service Object
**What goes wrong:** `pre_check` takes `gmail_service` as a parameter (line 66 of dispatcher.py) -- this is the raw Google API service, NOT the GmailClient wrapper. It uses it for `detect_human_reply()`.
**Why it happens:** pre_check was designed before GmailClient was created; it uses the lower-level service directly.
**How to avoid:** Pass `gmail_client._service` when calling `pre_check`, or refactor pre_check to accept GmailClient (mild breaking change to tests).
**Warning signs:** TypeError or AttributeError when calling pre_check.

### Pitfall 7: Campaign Processor Running Synchronously in Webhook Context
**What goes wrong:** The current `campaign_processor` callback in `initialize_services()` already handles async correctly via `asyncio.ensure_future`, but the EXTENDED version that also starts negotiations must ensure the negotiation handoff is also async and non-blocking.
**Why it happens:** The ClickUp webhook handler calls `_campaign_processor(task_id)` synchronously (line 117 of webhook.py).
**How to avoid:** Keep the existing pattern: `campaign_processor` is a sync function that schedules async work via `asyncio.ensure_future`.

### Pitfall 8: FastAPI Lifespan + Existing webhook_app
**What goes wrong:** `app.py` imports `app as webhook_app` from `campaign.webhook` and uses it as the FastAPI instance. But `webhook_app` is created with `FastAPI(title="Negotiation Agent Webhooks")` in webhook.py. The lifespan must be set on THIS app instance, not a new one.
**Why it happens:** The webhook module creates its own FastAPI app at module scope.
**How to avoid:** Either pass `lifespan` to `webhook_app` after import (via `webhook_app.router.lifespan_context = lifespan`), or restructure to create the FastAPI app in app.py and include the webhook router. The cleanest approach: create the FastAPI app in `create_app()` with `lifespan`, then `include_router` the webhook routes.
**Warning signs:** Lifespan handler never fires; on_event handlers still run.

## Code Examples

### Example 1: Building Negotiation Context Dict from Available Data
```python
def build_negotiation_context(
    influencer_row: InfluencerRow,
    campaign: Campaign,
    thread_id: str,
    round_count: int,
    cpm_tracker: CampaignCPMTracker | None = None,
) -> dict[str, Any]:
    """Assemble the negotiation_context dict that process_influencer_reply expects."""
    # Determine next CPM based on campaign range and tracker flexibility
    next_cpm = campaign.cpm_range.min_cpm  # Start at floor
    if cpm_tracker:
        flexibility = cpm_tracker.get_flexibility(
            influencer_engagement_rate=influencer_row.engagement_rate  # if available
        )
        next_cpm = flexibility.target_cpm

    return {
        "influencer_name": influencer_row.name,
        "influencer_email": influencer_row.email,
        "thread_id": thread_id,
        "platform": influencer_row.platform,
        "average_views": influencer_row.average_views,
        "deliverables_summary": campaign.target_deliverables,
        "deliverable_types": [d.deliverable_type for d in campaign.deliverables]
            if hasattr(campaign, 'deliverables') else [campaign.target_deliverables],
        "next_cpm": next_cpm,
        "client_name": campaign.client_name,
        "campaign_id": campaign.campaign_id,
        "history": "",  # Populated from previous rounds
    }
```

### Example 2: Inbound Email Processing Function
```python
async def process_inbound_email(
    gmail_client: GmailClient,
    message_id: str,
    dispatcher: SlackDispatcher,
    anthropic_client: Anthropic,
    negotiation_states: dict[str, Any],  # thread_id -> state dict
    audit_logger: AuditLogger,
) -> None:
    """Process a single inbound email through the full pipeline."""
    # Step 1: Fetch and parse the email (blocking -> thread)
    inbound = await asyncio.to_thread(gmail_client.get_message, message_id)

    # Step 2: Look up existing negotiation state by thread_id
    thread_state = negotiation_states.get(inbound.thread_id)
    if thread_state is None:
        logger.warning("No negotiation state for thread", thread_id=inbound.thread_id)
        return

    state_machine = thread_state["state_machine"]
    context = thread_state["context"]
    round_count = thread_state["round_count"]

    # Step 3: Run pre-check gates
    pre_check_result = dispatcher.pre_check(
        email_body=inbound.body_text,
        thread_id=inbound.thread_id,
        influencer_email=inbound.from_email,
        proposed_cpm=0.0,  # Will be refined after intent classification
        intent_confidence=1.0,  # Default before classification
        gmail_service=gmail_client._service,
        anthropic_client=anthropic_client,
    )
    if pre_check_result is not None:
        logger.info("Pre-check gate fired", action=pre_check_result["action"])
        return

    # Step 4: Run negotiation loop
    result = process_influencer_reply(
        email_body=inbound.body_text,
        negotiation_context=context,
        state_machine=state_machine,
        client=anthropic_client,
        round_count=round_count,
    )

    # Step 5: Dispatch to Slack
    result = dispatcher.handle_negotiation_result(result, context)

    # Step 6: If action is "send", send the reply
    if result["action"] == "send":
        await asyncio.to_thread(
            gmail_client.send_reply,
            inbound.thread_id,
            result["email_body"],
        )
        thread_state["round_count"] += 1
```

### Example 3: Gmail Watch Renewal Background Task
```python
async def renew_gmail_watch_periodically(
    gmail_client: GmailClient,
    topic: str,
    services: dict[str, Any],
    interval_hours: int = 144,  # 6 days (watch expires at 7)
) -> None:
    """Periodically renew Gmail watch to maintain push notifications."""
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            result = await asyncio.to_thread(gmail_client.setup_watch, topic)
            new_history_id = result.get("historyId", "")
            logger.info("Gmail watch renewed", history_id=new_history_id)
        except Exception:
            logger.exception("Failed to renew Gmail watch")
```

### Example 4: Starting Negotiations from Campaign Ingestion
```python
async def start_negotiations_for_campaign(
    found_influencers: list[dict[str, Any]],
    campaign: Campaign,
    gmail_client: GmailClient,
    anthropic_client: Anthropic,
    sheets_client: SheetsClient,
    negotiation_states: dict[str, Any],
) -> None:
    """Start negotiations for each found influencer from campaign ingestion."""
    cpm_tracker = CampaignCPMTracker(
        campaign_id=campaign.campaign_id,
        target_min_cpm=campaign.cpm_range.min_cpm,
        target_max_cpm=campaign.cpm_range.max_cpm,
        total_influencers=len(found_influencers),
    )

    for influencer_data in found_influencers:
        name = influencer_data["name"]
        sheet_data = influencer_data["sheet_data"]  # InfluencerRow

        # Calculate initial offer
        initial_rate = calculate_initial_offer(sheet_data.average_views)

        # Create state machine
        state_machine = NegotiationStateMachine()

        # Compose and send initial outreach email
        # ... compose email using campaign context + influencer data ...
        # ... send via gmail_client.send() ...
        # ... store state in negotiation_states[thread_id] ...

        state_machine.trigger("send_offer")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.95.0 (2023) | Deprecation warning; co-locates startup/shutdown |
| Separate startup/shutdown handlers | Single async context manager with yield | FastAPI 0.95.0 | Cleaner resource management |
| Gmail polling loops | Gmail Pub/Sub push notifications | Gmail API v1 (stable) | Lower latency, no wasted API calls |

**Deprecated/outdated in this codebase:**
- `@fastapi_app.on_event("startup")` and `@fastapi_app.on_event("shutdown")` in app.py lines 225-233 -- should be replaced with lifespan

## Key Design Decisions for Planner

### 1. Negotiation State Storage: In-Memory Dict
For v1, use a `dict[str, dict]` keyed by Gmail `thread_id` to store each active negotiation's state machine, round count, and context. This is lost on restart -- acceptable for v1, documented as a known limitation.

### 2. Gmail Notification: Push via Pub/Sub (Not Polling)
GmailClient.setup_watch() is already implemented. Add a `/webhooks/gmail` FastAPI route to receive Pub/Sub push notifications. This is more efficient than polling and already supported by the codebase.

### 3. Synchronous Google API Calls: Wrap in asyncio.to_thread
All GmailClient and SheetsClient methods are synchronous. Must wrap in `asyncio.to_thread()` in all async contexts to avoid blocking the event loop.

### 4. SlackDispatcher Initialization: Depends on SlackNotifier + ThreadStateManager
Both already exist in `initialize_services()`. SlackDispatcher additionally needs `EscalationTriggersConfig` (load from YAML) and `agent_email` (from env var).

### 5. Campaign-to-Negotiation Handoff: Extend campaign_processor
The existing `campaign_processor` callback in `initialize_services()` runs `audited_ingest()`. After it returns, consume `found_influencers` to start negotiations.

### 6. Restructure FastAPI App Creation
The webhook module creates its own FastAPI app at module scope. To use lifespan, either: (a) convert webhook routes to a FastAPI Router and include it, or (b) monkey-patch the lifespan onto the existing app. Option (a) is cleaner.

## Open Questions

1. **Pub/Sub endpoint security**
   - What we know: Gmail sends a Pub/Sub push notification to a publicly accessible URL. The notification includes subscription info.
   - What's unclear: Whether to verify the Pub/Sub message origin (Google sends a JWT bearer token for push subscriptions that can be verified).
   - Recommendation: For v1, accept all POST to `/webhooks/gmail` but validate the message structure. Add JWT verification as hardening in v2.

2. **Initial outreach email composition**
   - What we know: `compose_counter_email` exists for counter-offers. `calculate_initial_offer` computes the first price.
   - What's unclear: There is no `compose_initial_email` function. The initial outreach to an influencer may need a different email template than a counter-offer.
   - Recommendation: For v1, reuse `compose_counter_email` with `negotiation_stage="initial_outreach"` or create a simple template. This is a minor gap that can be handled in the plan.

3. **Thread-to-campaign mapping for inbound emails**
   - What we know: Inbound emails arrive with a `thread_id`. The negotiation state dict can be keyed by thread_id.
   - What's unclear: How to map a brand-new inbound email (not in any active negotiation) to ignore it vs. process it.
   - Recommendation: Only process emails for thread_ids in the active negotiation state dict. Unknown threads are logged and ignored.

4. **Pre-check CPM and confidence before classification**
   - What we know: `SlackDispatcher.pre_check()` takes `proposed_cpm` and `intent_confidence` as parameters, but these are only known AFTER `classify_intent` runs.
   - What's unclear: The pre_check is designed to run BEFORE the negotiation loop. The CPM and confidence values at pre_check time are unknowns.
   - Recommendation: Pass 0.0 for proposed_cpm and 1.0 for intent_confidence in pre_check (only human takeover and human reply detection gates will fire). The CPM and intent triggers will fire inside `process_influencer_reply` instead, which already handles escalation for those cases.

## Sources

### Primary (HIGH confidence)
- **Codebase analysis** -- all source files read directly:
  - `src/negotiation/app.py` (303 lines) -- current entry point
  - `src/negotiation/llm/negotiation_loop.py` (168 lines) -- process_influencer_reply
  - `src/negotiation/slack/dispatcher.py` (409 lines) -- SlackDispatcher
  - `src/negotiation/campaign/ingestion.py` (348 lines) -- ingest_campaign
  - `src/negotiation/campaign/cpm_tracker.py` (187 lines) -- CampaignCPMTracker
  - `src/negotiation/email/client.py` (216 lines) -- GmailClient
  - `src/negotiation/audit/wiring.py` (271 lines) -- audit wrappers
  - `src/negotiation/campaign/webhook.py` (132 lines) -- ClickUp webhook + set_campaign_processor
  - `src/negotiation/state_machine/machine.py` -- NegotiationStateMachine
  - `src/negotiation/domain/models.py` -- NegotiationContext, PayRange
  - `src/negotiation/sheets/client.py` -- SheetsClient with get_pay_range
  - `src/negotiation/pricing/engine.py` -- calculate_initial_offer, calculate_rate
  - `src/negotiation/llm/client.py` -- get_anthropic_client, model constants
  - `src/negotiation/auth/credentials.py` -- get_gmail_service, get_gmail_credentials
  - `src/negotiation/slack/triggers.py` -- EscalationTriggersConfig, load_triggers_config
  - `tests/test_app.py` -- existing test patterns
- **`.planning/v1.0-MILESTONE-AUDIT.md`** -- gap identification (MISSING-01 through MISSING-04, tech debt)
- **`.planning/REQUIREMENTS.md`** -- all 22 v1 requirements and their phase mapping

### Secondary (MEDIUM confidence)
- [FastAPI Lifespan Events - Official Docs](https://fastapi.tiangolo.com/advanced/events/) -- lifespan context manager pattern
- [Gmail API Push Notifications - Google Developers](https://developers.google.com/workspace/gmail/api/guides/push) -- Pub/Sub push notification flow, watch renewal, history ID usage

### Tertiary (LOW confidence)
- None -- all findings verified against codebase and official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use; no new dependencies
- Architecture: HIGH -- all components exist, patterns verified by reading source code
- Pitfalls: HIGH -- identified from direct code analysis (sync/async mismatch, missing context keys, history ID tracking)
- Wiring approach: HIGH -- milestone audit explicitly identifies every gap and its location

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable -- no library changes expected)
