---
phase: 06-runtime-orchestration-wiring
verification_status: passed
verified_at: 2026-02-19
tests_passing: 681
---

# Phase 6 Verification: Runtime Orchestration Wiring

## Goal Check

**Phase Goal**: All Phase 1-5 components are connected in the runtime entry point so the agent can receive emails, run the negotiation loop, dispatch Slack notifications, and start negotiations from campaign ingestion — delivering the core value end-to-end.

**Verdict**: ACHIEVED. The `src/negotiation/app.py` file is a substantive, fully-wired runtime orchestration entry point — not a stub. All five component domains (Gmail, negotiation loop, Slack, campaign ingestion, pricing/CPM) are initialized and connected through working wiring functions. The full test suite of 681 tests passes with zero regressions.

---

## Success Criteria Verification

### SC-1: Inbound Email to Negotiation Loop (End-to-End)

**Status**: PASS

**What was verified**: The `process_inbound_email` async function in `app.py` (lines 609-726) implements the complete pipeline:

1. `gmail_client.get_message(message_id)` — fetches inbound email (line 628)
2. Thread lookup against `negotiation_states` dict — guards against unknown threads (lines 637-643)
3. `dispatcher.pre_check(...)` — runs pre-check gate with human takeover detection (lines 651-667)
4. `audited_process_reply(...)` — runs the negotiation loop with audit logging (lines 682-688)
5. `dispatcher.handle_negotiation_result(result, context)` — routes result to Slack (lines 691-692)
6. `gmail_client.send_reply(thread_id, email_body)` — sends counter-offer when action is "send" (lines 696-701)

This function is triggered by the Gmail Pub/Sub webhook at `POST /webhooks/gmail` (line 563), which calls `asyncio.ensure_future(process_inbound_email(msg_id, svc))` for each new message ID (line 599). Gmail watch is registered on lifespan startup (lines 529-540) and renewed every 6 days by `renew_gmail_watch_periodically` (lines 729-752).

**Test evidence**: `tests/test_orchestration.py::TestProcessInboundEmail::test_full_pipeline` — verifies `get_message`, `pre_check`, `process_reply`, and `send_reply` all called in sequence. All 4 `TestProcessInboundEmail` tests pass.

---

### SC-2: Campaign Ingestion to Negotiation Start

**Status**: PASS

**What was verified**: The `campaign_processor` closure in `initialize_services` (lines 269-312) is registered via `set_campaign_processor(campaign_processor)` (line 312). When a ClickUp webhook fires, this processor:

1. Calls `audited_ingest(task_id, clickup_token, sheets_client, slack_notifier)` — runs campaign ingestion with audit logging (line 276-281)
2. Extracts `found_influencers` and `campaign` from the result (lines 283-284)
3. Calls `start_negotiations_for_campaign(found_influencers, campaign, services)` when influencers are found and GmailClient is available (lines 286-295)

`start_negotiations_for_campaign` (lines 368-510) iterates each influencer and:
1. Retrieves PayRange via `calculate_initial_offer(sheet_data.average_views)` (line 423)
2. Creates `NegotiationStateMachine()` (line 426)
3. Composes initial outreach email with `compose_counter_email(..., negotiation_stage="initial_outreach", ...)` (lines 436-448)
4. Sends via `gmail_client.send(outbound)` as a new thread (line 464)
5. Stores full negotiation state in `negotiation_states[thread_id]` (lines 480-486)
6. Logs to audit trail via `audit_logger.log_email_sent(...)` (lines 489-497)

**Test evidence**: `tests/test_orchestration.py::TestStartNegotiationsForCampaign::test_creates_state_entries` — verifies state entry created, Gmail send called, state machine triggered, and audit logged. All 4 `TestStartNegotiationsForCampaign` tests pass.

---

### SC-3: SlackDispatcher Pre-Check Gate Before Every Negotiation Loop Iteration

**Status**: PASS

**What was verified**: In `process_inbound_email`, the pre-check gate runs at Step 3 (lines 650-667) before the negotiation loop runs at Step 4 (lines 670-688). The pre-check call passes all required parameters:

```python
pre_check_result = dispatcher.pre_check(
    email_body=inbound.body_text,
    thread_id=inbound.thread_id,
    influencer_email=inbound.from_email,
    proposed_cpm=0.0,
    intent_confidence=1.0,
    gmail_service=gmail_client._service,
    anthropic_client=anthropic_client,
)
```

If `pre_check_result is not None`, the function returns early — the negotiation loop is NOT called (line 667). The dispatcher is also called at Step 5 via `dispatcher.handle_negotiation_result(result, context)` (line 692) to route escalations and agreements to Slack.

SlackDispatcher is initialized in `initialize_services` (lines 211-233) with `SlackNotifier`, `ThreadStateManager`, `triggers_config`, and `agent_email`. Audit logging is wired to the dispatcher via `wire_audit_to_dispatcher(slack_dispatcher, audit_logger)` (lines 244-248).

**Test evidence**: `tests/test_orchestration.py::TestProcessInboundEmail::test_stops_on_precheck_gate` — verifies `process_reply` is NOT called when pre-check returns non-None. `test_handles_escalation` — verifies `handle_negotiation_result` is called and `send_reply` is NOT called for escalations.

---

### SC-4: All Email Sends, Receives, Escalations, and Agreements Logged to Audit Trail

**Status**: PASS

**What was verified**: Audit wiring is applied at three levels in `initialize_services`:

1. **SlackDispatcher audit wiring** (lines 244-248): `wire_audit_to_dispatcher(slack_dispatcher, audit_logger)` — wraps dispatcher's escalation and agreement notifications with audit logging.

2. **Process reply audit wiring** (lines 251-257): `create_audited_process_reply(process_influencer_reply, audit_logger)` — wraps the negotiation loop function so all replies processed are logged.

3. **Campaign ingestion audit wiring** (lines 260-261): `wire_audit_to_campaign_ingestion(ingest_campaign, audit_logger)` — wraps ingestion so all campaigns processed are logged.

4. **Initial outreach audit logging** (lines 489-497): `audit_logger.log_email_sent(...)` called directly in `start_negotiations_for_campaign` for each initial email sent.

The `audited_process_reply` function is used in `process_inbound_email` at line 674 with fallback to raw `process_influencer_reply` if unavailable.

**Test evidence**: `test_creates_state_entries` verifies `mock_audit.log_email_sent.assert_called_once()`. `test_configures_error_notifier_when_slack_available` verifies error notifier configuration.

---

### SC-5: CampaignCPMTracker Instantiated Per Campaign with Per-Influencer Flexibility

**Status**: PASS

**What was verified**: In `start_negotiations_for_campaign` (lines 402-415), `CampaignCPMTracker` is instantiated once per campaign:

```python
cpm_tracker = CampaignCPMTracker(
    campaign_id=campaign.campaign_id,
    target_min_cpm=campaign.cpm_range.min_cpm,
    target_max_cpm=campaign.cpm_range.max_cpm,
    total_influencers=len(found_influencers),
)
```

The tracker is passed to `build_negotiation_context` (line 472), where it provides per-influencer flexibility:

```python
flexibility = cpm_tracker.get_flexibility(
    influencer_engagement_rate=engagement_rate,
)
next_cpm = flexibility.target_cpm
```

The tracker is also stored in `negotiation_states[thread_id]["cpm_tracker"]` (line 485) for use during subsequent negotiation rounds.

**Test evidence**: `tests/test_orchestration.py::TestStartNegotiationsForCampaign::test_instantiates_cpm_tracker` — verifies `CampaignCPMTracker` constructed with correct campaign CPM range and tracker stored in state entry. `TestBuildNegotiationContext::test_uses_cpm_tracker_flexibility` — verifies `get_flexibility` is called and `target_cpm` used as `next_cpm`.

---

### SC-6: Deprecated FastAPI on_event Pattern Replaced with Lifespan

**Status**: PASS

**What was verified**: The `lifespan` function uses `@asynccontextmanager` (lines 513-547) and is passed directly to `FastAPI(lifespan=lifespan)` at line 559. The source of `create_app` contains no reference to `on_event`.

Code evidence:
- Line 23: `from contextlib import asynccontextmanager`
- Line 513: `@asynccontextmanager`
- Line 514: `async def lifespan(app: FastAPI) -> AsyncGenerator[None]:`
- Line 559: `fastapi_app = FastAPI(title="Negotiation Agent Webhooks", lifespan=lifespan)`
- Zero occurrences of `on_event` in `app.py` (grep confirmed no matches)

**Test evidence**: `tests/test_app.py::TestCreateApp::test_create_app_uses_lifespan` — asserts `app.router.lifespan_context is not None`. `tests/test_app.py::TestCreateApp::test_no_deprecated_on_event` — asserts `"on_event" not in inspect.getsource(create_app)`.

---

## Gap Closure Verification

The phase claims to close 4 MISSING gaps and 2 broken flows from the v1.0 milestone audit.

### MISSING-01: process_influencer_reply not wired to inbound email handler

**Closed**: `process_inbound_email` calls `audited_process_reply` (or `process_influencer_reply` as fallback) at line 682. The `audited_process_reply` is created in `initialize_services` via `create_audited_process_reply(process_influencer_reply, audit_logger)` (lines 251-257).

### MISSING-02: No Gmail Pub/Sub webhook endpoint

**Closed**: `POST /webhooks/gmail` endpoint registered at line 563. It decodes the Pub/Sub message, fetches new messages via `gmail.fetch_new_messages`, and dispatches each to `process_inbound_email` as an async background task (lines 591-601).

### MISSING-03: SlackDispatcher not wired to negotiation loop

**Closed**: `dispatcher.pre_check(...)` runs before the loop (line 651). `dispatcher.handle_negotiation_result(result, context)` runs after the loop (line 692). `wire_audit_to_dispatcher` wires audit logging to the dispatcher (line 247).

### MISSING-04: Campaign ingestion result not used to start negotiations

**Closed**: `campaign_processor` extracts `found_influencers` from the `audited_ingest` result (line 283) and calls `start_negotiations_for_campaign(...)` (line 286). `start_negotiations_for_campaign` creates state machine, sends initial emails, and stores negotiation state.

### Broken Flow 1: No lifespan (on_event deprecated)

**Closed**: `@asynccontextmanager lifespan` function implemented (lines 513-547), passed to `FastAPI(lifespan=lifespan)` (line 559). Gmail watch registered on startup, audit DB closed on shutdown.

### Broken Flow 2: CampaignCPMTracker not wired to negotiation context

**Closed**: `CampaignCPMTracker` instantiated in `start_negotiations_for_campaign` (line 410), passed to `build_negotiation_context` (line 472), stored in `negotiation_states[thread_id]` (line 485). The `build_negotiation_context` helper queries `cpm_tracker.get_flexibility(...)` and uses `flexibility.target_cpm` as `next_cpm` (lines 341-346).

---

## Test Coverage

| Test File | Tests | Result |
|---|---|---|
| `tests/test_app.py` | 23 | All PASS |
| `tests/test_orchestration.py` | 11 | All PASS |
| Full suite (681 total) | 681 | All PASS |

**Phase 6 new tests (20 total)**:

- 9 tests added to `test_app.py`: GmailClient/SlackDispatcher/Anthropic initialization, graceful degradation, lifespan context manager, no-on_event assertion, `/webhooks/gmail` route existence
- 11 tests in `test_orchestration.py`: `build_negotiation_context` (3 tests), `process_inbound_email` (4 tests — full pipeline, unknown thread skip, pre-check gate stop, escalation handling), `start_negotiations_for_campaign` (4 tests — state entry creation, no-Gmail skip, no-Anthropic skip, CPMTracker instantiation)

No regressions: all 661 pre-existing tests continue to pass.

---

## Anti-Patterns Scan

No blocking anti-patterns found in `src/negotiation/app.py`:

- No `return null` / `return {}` stubs — all functions have substantive implementations
- No `TODO`/`FIXME`/`PLACEHOLDER` comments — the single acknowledged limitation (in-memory state lost on restart) is documented in a decision note, not as a TODO
- No `console.log`-only or `preventDefault`-only handlers
- No empty API route implementations
- `on_event` deprecated pattern: absent (confirmed by grep returning no matches)

One design acknowledgment in the code (not a blocker): the in-memory `negotiation_states` dict is keyed by `thread_id` and is lost on process restart. This is explicitly documented as a v1 limitation in the SUMMARY.md and the code. It does not block the phase goal.

---

## Human Verification Required

None — all success criteria are verifiable through code inspection and test execution.

---

## Verdict

**Status: PASSED**

**Score**: 6/6 success criteria verified

All six success criteria are met by substantive, wired implementations in `src/negotiation/app.py`. The code is not a stub: it initializes nine distinct service types, wires three layers of audit logging, implements the complete inbound email pipeline in `process_inbound_email`, implements the campaign-to-negotiation handoff in `start_negotiations_for_campaign`, and replaces deprecated patterns with the correct FastAPI lifespan context manager.

The full test suite of 681 tests passes (661 original + 20 new), confirming both correctness and absence of regressions. All 4 MISSING gaps and 2 broken flows from the v1.0 milestone audit are closed with working code and test coverage.

---

_Verified: 2026-02-19T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
