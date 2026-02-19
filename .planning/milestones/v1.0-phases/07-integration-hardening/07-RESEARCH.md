# Phase 7: Integration Hardening - Research

**Researched:** 2026-02-19
**Domain:** Python codebase surgery — bug fixes, audit wiring, model extension, orphan cleanup
**Confidence:** HIGH (all findings from direct source code inspection)

## Summary

Phase 7 is pure codebase surgery: no new libraries, no architectural changes, no external research needed. All five issues were identified by direct inspection of the source files. The fixes are small, surgical, and high-confidence because every affected file already has comprehensive test coverage that shows exactly what the expected behavior is.

The four bug categories are: (1) a None-guard missing in `ingest_campaign` that crashes when Slack is unconfigured, (2) a hardcoded `proposed_cpm=0.0` and `intent_confidence=1.0` in `process_inbound_email` that disables live CPM/intent pre-check gates, (3) a missing `engagement_rate` field on `InfluencerRow` that causes `CampaignCPMTracker.get_flexibility()` to always receive `None` and never apply engagement premiums, and (4) two orphaned functions (`create_audited_email_receive` in `audit/wiring.py`, `get_pay_range` in `sheets/client.py`) that are fully implemented and tested but never called from the live pipeline. Additionally, the `log_email_received` method exists on `AuditLogger` but is never called when inbound emails arrive, leaving a gap in the DATA-03 audit trail requirement.

The test suite is 681 tests, all currently passing. Every fix needs regression-safe tests added to the relevant test files. The existing test patterns (class-based, `MagicMock`, `pytest.mark.anyio()` for async, `asyncio.run()` for sync async tests) must be followed.

**Primary recommendation:** Fix each issue in its source file with a targeted one-to-five line change, add tests to the corresponding existing test file, and verify `681 + N tests pass` with no regressions.

---

## Standard Stack

No new libraries required. The entire fix set uses only what is already installed.

### Core (already installed, no changes needed)

| Library | Version | Purpose | Already Used In |
|---------|---------|---------|-----------------|
| pydantic v2 | >=2.12,<3 | `InfluencerRow` model extension | `src/negotiation/sheets/models.py` |
| structlog | >=25.5.0 | Logging pattern already in use | All production modules |
| pytest-anyio | 4.12.1 | Async test runner for `@pytest.mark.anyio()` | `tests/campaign/test_ingestion.py` |
| pytest | >=9.0 | Test framework | All test files |

**Installation:** None needed — all dependencies already present in `.venv`.

---

## Architecture Patterns

### Existing Project Structure (relevant to this phase)

```
src/negotiation/
├── campaign/
│   ├── ingestion.py       # ISSUE-01 fix: add None-guard around slack_notifier calls
│   └── cpm_tracker.py     # Uses engagement_rate from InfluencerRow (ISSUE-03 consumer)
├── sheets/
│   ├── models.py          # ISSUE-03 fix: add engagement_rate field
│   └── client.py          # Orphan: get_pay_range — review decision
├── app.py                 # ISSUE-02 fix: pass real CPM/intent; MISSING-A: call log_email_received
├── audit/
│   ├── logger.py          # log_email_received method exists but never called
│   └── wiring.py          # Orphan: create_audited_email_receive — review decision
tests/
├── campaign/
│   └── test_ingestion.py  # Add ISSUE-01 None-guard regression tests here
├── sheets/
│   └── test_models.py     # Add ISSUE-03 engagement_rate field tests here
├── audit/
│   └── test_wiring.py     # Add MISSING-A audit logging tests here
└── test_orchestration.py  # Add ISSUE-02 and MISSING-A pipeline tests here
```

### Pattern 1: None-guard on optional service calls

**What:** Wrap calls to optional services (those that can be `None` when env vars are absent) with `if service is not None:` before calling methods.

**When to use:** Any call to `slack_notifier`, `gmail_client`, `anthropic_client`, `sheets_client`, `slack_dispatcher` — all are optional services.

**Example (ISSUE-01 fix in `ingestion.py`):**
```python
# Source: direct inspection of src/negotiation/campaign/ingestion.py lines 286-342
# BEFORE (crashes when slack_notifier is None):
slack_notifier.post_escalation(blocks=[...], fallback_text="...")
for name in missing_influencers:
    slack_notifier.post_escalation(blocks=[...], fallback_text="...")

# AFTER (graceful degradation):
if slack_notifier is not None:
    slack_notifier.post_escalation(blocks=[...], fallback_text="...")
for name in missing_influencers:
    if slack_notifier is not None:
        slack_notifier.post_escalation(blocks=[...], fallback_text="...")
```

**Verification:** The existing test `test_slack_notifier_none_when_no_token` in `tests/test_app.py` already confirms `initialize_services()` sets `slack_notifier=None`. The `ingest_campaign` function must not crash when called with `slack_notifier=None`.

### Pattern 2: Adding an optional field to a frozen Pydantic v2 model

**What:** Add a field with a default of `None` (typed `float | None`) to a `ConfigDict(frozen=True)` Pydantic model. Existing instantiation sites pass no keyword argument for the new field — they get `None` automatically.

**When to use:** ISSUE-03 fix — `InfluencerRow` needs `engagement_rate: float | None = None`.

**Example (ISSUE-03 fix in `models.py`):**
```python
# Source: direct inspection of src/negotiation/sheets/models.py
# Add after the existing max_rate field:
engagement_rate: float | None = None
```

**Important:** The `SheetsClient.get_all_influencers()` method builds `InfluencerRow` from Google Sheets records. The Sheet may or may not have an "Engagement Rate" column. Use `.get("Engagement Rate")` which returns `None` if the column is absent — safe to pass as `engagement_rate` since the field accepts `None`. No coercion needed (engagement_rate is `float | None`, not Decimal).

**Existing `InfluencerRow` construction in `sheets/client.py` at line 75:**
```python
rows.append(
    InfluencerRow(
        name=str(record["Name"]),
        email=str(record["Email"]),
        platform=str(record["Platform"]),
        handle=str(record["Handle"]),
        average_views=int(record["Average Views"]),
        min_rate=record["Min Rate"],
        max_rate=record["Max Rate"],
        # ADD: engagement_rate=record.get("Engagement Rate"),
    )
)
```

**What changes in cpm_tracker:** `build_negotiation_context` in `app.py` already reads `engagement_rate` via `getattr(sheet_data, "engagement_rate", None)` (line 343). Once `InfluencerRow` has the field, `getattr` returns the real value instead of `None`. The `CampaignCPMTracker.get_flexibility(influencer_engagement_rate=...)` then computes real premiums.

### Pattern 3: Direct audit log call in the inbound email pipeline

**What:** Call `audit_logger.log_email_received(...)` directly in `process_inbound_email` in `app.py`, immediately after the email is fetched and the thread state is confirmed active.

**When to use:** MISSING-A — inbound emails arrive via `process_inbound_email` but are never logged.

**Where to insert (in `app.py` `process_inbound_email` function):**
```python
# Source: direct inspection of src/negotiation/app.py
# After line 647 (thread_state found, state_machine and context extracted),
# BEFORE the pre_check gate at line 650:
audit_logger = services.get("audit_logger")
if audit_logger is not None:
    audit_logger.log_email_received(
        campaign_id=context.get("campaign_id"),
        influencer_name=str(context.get("influencer_name", "")),
        thread_id=inbound.thread_id,
        email_body=inbound.body_text,
        negotiation_state=str(context.get("negotiation_state", "")),
        intent_classification=None,  # Not yet classified at receipt
    )
```

**Note:** `audit_logger` is always in `services` (initialized unconditionally in `initialize_services`). The `services.get("audit_logger")` pattern matches existing code style.

### Pattern 4: Passing real CPM/intent values to pre_check (ISSUE-02)

**What:** Replace the hardcoded `proposed_cpm=0.0, intent_confidence=1.0` in the `pre_check` call with values extracted from the email context or computed from available data.

**Where:** `app.py`, `process_inbound_email` function, lines 651-659 (the `dispatcher.pre_check(...)` call).

**Current buggy code:**
```python
# Source: direct inspection of src/negotiation/app.py lines 651-659
pre_check_result = dispatcher.pre_check(
    email_body=inbound.body_text,
    thread_id=inbound.thread_id,
    influencer_email=inbound.from_email,
    proposed_cpm=0.0,           # HARDCODED -- disables CPM gate
    intent_confidence=1.0,       # HARDCODED -- disables intent gate
    gmail_service=gmail_client._service,
    anthropic_client=anthropic_client,
)
```

**Fix strategy:** The `proposed_cpm` should come from the negotiation context (`context.get("next_cpm", 0.0)`) which tracks the current CPM in negotiation. The `intent_confidence` should default to `0.0` (unknown) when no classification has been done yet — letting the pre_check gate actually fire when CPM or intent thresholds are exceeded. However, verify what `SlackDispatcher.pre_check` actually expects before choosing the right defaults.

**Research finding:** The `intent_confidence` parameter semantics need verification against `src/negotiation/slack/dispatcher.py`. A value of `1.0` means "fully confident" which could suppress escalation gates. A value of `0.0` means "no confidence" which would trigger different behavior. The fix needs to match actual dispatcher contract.

### Pattern 5: Orphan function decision — connect or delete

**What:** `create_audited_email_receive` (in `audit/wiring.py`) and `get_pay_range` (in `sheets/client.py`) are fully implemented, tested, and exported but called from nowhere in the live pipeline.

**Decision framework:**
- `create_audited_email_receive`: The MISSING-A fix (Pattern 3 above) uses `audit_logger.log_email_received()` directly rather than through a wrapper. This means `create_audited_email_receive` remains a valid but unused utility. Decision: **remove from `__init__.py` exports if not wired, OR wire it** if the approach is to wrap the receive action rather than call directly.
- `get_pay_range` on `SheetsClient`: The live pipeline uses `find_influencer()` directly (returns `InfluencerRow`), not `get_pay_range()` (returns `PayRange`). The method is tested. Decision: **keep as a utility** (it provides a valid abstraction) but add a `# pragma: no cover` or explicitly document it as a utility method not in the hot path. Or remove if the team wants to minimize surface area.

**Recommended resolution:**
- `create_audited_email_receive`: Wire it OR delete it. If MISSING-A is fixed via direct `log_email_received()` call (Pattern 3), delete `create_audited_email_receive` from `__init__.py` exports to reduce surface area. Keep the implementation if useful later.
- `get_pay_range`: Keep on `SheetsClient` — it's a useful convenience method. No code change needed. The "orphan" label from the audit means it is unused in the current pipeline, not that it is wrong.

### Anti-Patterns to Avoid

- **Do not remove `create_audited_email_receive` from `wiring.py`**: Tests in `tests/audit/test_wiring.py` (lines 73-114) directly test this function. Removing it breaks 2 tests. Instead, either keep it or update the test file simultaneously.
- **Do not use `asyncio.run()` for new async tests**: The existing ingestion tests use `@pytest.mark.anyio()` for async tests. Follow the same pattern.
- **Do not forget the `# type: ignore` consideration**: `InfluencerRow` is `frozen=True`. Adding a new field with a default of `None` is valid in Pydantic v2 — no special handling needed. But ensure the `field_validator` for `coerce_from_sheet_float` is NOT applied to `engagement_rate` (it should only apply to `min_rate`, `max_rate`).
- **Do not break existing ingestion tests**: The three `test_ingestion.py` async tests (`test_all_influencers_found`, `test_some_influencers_missing`, `test_all_influencers_missing`) all pass `slack_notifier=MagicMock()`. After the ISSUE-01 fix, these tests must still pass (the guard only applies when `slack_notifier is None`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audit logging of received emails | New audit wrapper class | `audit_logger.log_email_received()` directly | Already exists in `AuditLogger`, tested, complete |
| CPM extraction from context | New CPM parsing logic | `context.get("next_cpm", Decimal("0"))` | Already stored in negotiation context |
| Optional field with None default | Custom validator | Pydantic v2 `field: float \| None = None` | Pydantic handles this natively |
| Orphan detection | New analysis tooling | Direct grep/inspection | Already done — findings documented here |

**Key insight:** Every piece of infrastructure needed already exists. The bugs are wiring gaps, not missing features.

---

## Common Pitfalls

### Pitfall 1: Breaking existing test assertions on `post_escalation` call count

**What goes wrong:** The existing test `test_all_influencers_found` asserts `slack_notifier.post_escalation.call_count == 1`. If the None-guard changes the call semantics, this assertion may need updating.

**Why it happens:** The tests use `slack_notifier = MagicMock()` (not None), so the guard only fires when `slack_notifier` IS None. The existing tests should continue to pass unchanged after the fix.

**How to avoid:** Confirm the guard is `if slack_notifier is not None:` — this means `MagicMock()` is truthy and the calls still happen in existing tests. Only `None` triggers the skip.

**Warning signs:** Any existing `test_all_influencers_found` or `test_some_influencers_missing` failure after the fix.

### Pitfall 2: Pydantic v2 frozen model field addition

**What goes wrong:** Adding a field to a `frozen=True` Pydantic model can break if existing tests construct the model with positional args or if the field order matters for serialization.

**Why it happens:** Pydantic v2 frozen models are immutable after creation but can have new optional fields added freely as long as they have defaults.

**How to avoid:** Add `engagement_rate: float | None = None` as the last field in `InfluencerRow`. This ensures all existing constructor calls (which omit the field) continue to work without modification. Verify `test_models.py` tests still pass.

**Warning signs:** Any `ValidationError` from existing `InfluencerRow(...)` calls without `engagement_rate=`.

### Pitfall 3: `intent_confidence` semantics in `SlackDispatcher.pre_check`

**What goes wrong:** Passing wrong default for `intent_confidence` could suppress legitimate escalations or fire gates when they shouldn't.

**Why it happens:** The audit noted `intent_confidence=1.0` disables intent pre-check triggers — but the exact mechanism (is `1.0` "max confidence = suppress" or "no filter"?) must be confirmed by reading the dispatcher.

**How to avoid:** Read `src/negotiation/slack/dispatcher.py` `pre_check` method before fixing ISSUE-02. Determine whether `intent_confidence` is used as a threshold filter (e.g., "only fire gate if confidence < X") or as a direct value passed to a trigger condition.

**Warning signs:** Pre-check gate tests in `tests/slack/test_dispatcher.py` failing after ISSUE-02 fix.

### Pitfall 4: `audit_logger` key may not exist in all `services` dicts in tests

**What goes wrong:** When adding `services.get("audit_logger")` to `process_inbound_email`, tests that build a `services` dict without `"audit_logger"` will return `None` — which is safe if the guard is `if audit_logger is not None`.

**Why it happens:** The `_base_services()` helper in `test_orchestration.py` (line 86-106) already includes `"audit_logger": audit_logger or MagicMock()` as a default. Existing tests are safe.

**How to avoid:** Use `services.get("audit_logger")` (not `services["audit_logger"]`) in the fix to avoid KeyError. The `_base_services` fixture already provides a MagicMock audit_logger.

**Warning signs:** `KeyError: 'audit_logger'` in test output.

### Pitfall 5: `create_audited_email_receive` is already tested — don't delete without updating tests

**What goes wrong:** If the decision is to remove `create_audited_email_receive` from `__init__.py` exports, the test `TestCreateAuditedEmailReceive` in `tests/audit/test_wiring.py` (lines 73-114) imports it and will fail on collection.

**Why it happens:** The audit described it as "orphaned" from the pipeline, not as broken. Tests for it exist and pass.

**How to avoid:** Decision options: (a) Keep it exported and tested, mark as utility; (b) Wire it into `process_inbound_email` as the receive wrapper instead of calling `log_email_received` directly; (c) Remove it from `__init__.py` but keep the function + tests (just don't export). Do not delete the function or its tests without explicitly choosing option (c).

---

## Code Examples

Verified patterns from direct source inspection:

### ISSUE-01 Fix: Null-guard pattern in `ingestion.py`

```python
# Source: src/negotiation/campaign/ingestion.py lines 286-342
# Pattern already used in app.py (lines 113-132): check before calling optional service

# Step 6: Post Slack notification that campaign ingestion started
if slack_notifier is not None:
    slack_notifier.post_escalation(
        blocks=[...],
        fallback_text="...",
    )

# Step 7: Post individual Slack alerts for each missing influencer
for name in missing_influencers:
    if slack_notifier is not None:
        slack_notifier.post_escalation(
            blocks=[...],
            fallback_text="...",
        )
```

### ISSUE-03 Fix: Adding `engagement_rate` to `InfluencerRow`

```python
# Source: src/negotiation/sheets/models.py
# Add engagement_rate as optional field with None default:
class InfluencerRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    email: str
    platform: Platform
    handle: str
    average_views: int
    min_rate: Decimal
    max_rate: Decimal
    engagement_rate: float | None = None   # ADD THIS LINE

    @field_validator("min_rate", "max_rate", mode="before")
    @classmethod
    def coerce_from_sheet_float(cls, v: object) -> object:
        # ... existing validator unchanged ...
```

### MISSING-A Fix: Calling `log_email_received` in `process_inbound_email`

```python
# Source: src/negotiation/app.py — insert after line 647 (context extracted)
# Before the pre_check gate:
audit_logger = services.get("audit_logger")
if audit_logger is not None:
    audit_logger.log_email_received(
        campaign_id=context.get("campaign_id"),
        influencer_name=str(context.get("influencer_name", "")),
        thread_id=inbound.thread_id,
        email_body=inbound.body_text,
        negotiation_state=str(context.get("negotiation_state", "")),
        intent_classification=None,
    )
```

### ISSUE-03: Wiring engagement_rate through `SheetsClient`

```python
# Source: src/negotiation/sheets/client.py line 75
# In get_all_influencers, after max_rate:
rows.append(
    InfluencerRow(
        name=str(record["Name"]),
        email=str(record["Email"]),
        platform=str(record["Platform"]),
        handle=str(record["Handle"]),
        average_views=int(record["Average Views"]),
        min_rate=record["Min Rate"],
        max_rate=record["Max Rate"],
        engagement_rate=record.get("Engagement Rate"),  # ADD THIS
    )
)
```

### Test pattern for new async tests (follows existing ingestion test style)

```python
# Source: tests/campaign/test_ingestion.py — uses pytest-anyio 4.12.1
@pytest.mark.anyio()
async def test_ingest_campaign_no_slack_notifier_does_not_crash(
    tmp_path: Path,
    mock_influencer_row: InfluencerRow,
) -> None:
    """When slack_notifier is None, ingest_campaign completes without error."""
    config_path = _write_config(tmp_path, "...")

    mock_response = MagicMock()
    mock_response.json.return_value = {...}
    mock_response.raise_for_status = MagicMock()

    sheets_client = MagicMock()
    sheets_client.find_influencer.return_value = mock_influencer_row

    with patch("negotiation.campaign.ingestion.httpx.AsyncClient") as mock_httpx:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        # This should not raise AttributeError: 'NoneType' object has no attribute 'post_escalation'
        result = await ingest_campaign(
            task_id="task_001",
            api_token="test-token",
            sheets_client=sheets_client,
            slack_notifier=None,   # KEY: None means no Slack
            config_path=config_path,
        )

    assert isinstance(result["campaign"], Campaign)
    assert len(result["found_influencers"]) == 1
```

### Test pattern for `InfluencerRow` with `engagement_rate`

```python
# Source: tests/sheets/test_models.py — class-based, _make() helper pattern
def test_engagement_rate_defaults_to_none(self) -> None:
    """engagement_rate field defaults to None when not provided."""
    row = self._make()  # existing _make() omits engagement_rate
    assert row.engagement_rate is None

def test_engagement_rate_accepts_float(self) -> None:
    """engagement_rate accepts a float value."""
    row = self._make(engagement_rate=4.5)
    assert row.engagement_rate == 4.5

def test_engagement_rate_accepts_none_explicitly(self) -> None:
    """engagement_rate accepts explicit None."""
    row = self._make(engagement_rate=None)
    assert row.engagement_rate is None
```

---

## Issue-by-Issue Fix Map

| Issue | File to Change | Line(s) | Change Type | Test File | Test Class |
|-------|---------------|---------|-------------|-----------|------------|
| ISSUE-01 | `src/negotiation/campaign/ingestion.py` | 287, 323 | Add `if slack_notifier is not None:` guard | `tests/campaign/test_ingestion.py` | `TestIngestCampaign` |
| ISSUE-02 | `src/negotiation/app.py` | 655-656 | Replace hardcoded `0.0`/`1.0` with real values | `tests/test_orchestration.py` | `TestProcessInboundEmail` |
| ISSUE-03a | `src/negotiation/sheets/models.py` | after line 32 | Add `engagement_rate: float \| None = None` | `tests/sheets/test_models.py` | `TestInfluencerRow` |
| ISSUE-03b | `src/negotiation/sheets/client.py` | line 84 | Add `engagement_rate=record.get("Engagement Rate")` | `tests/sheets/test_client.py` | existing sheet client tests |
| MISSING-A | `src/negotiation/app.py` | after line 647 | Add `audit_logger.log_email_received(...)` call | `tests/test_orchestration.py` | `TestProcessInboundEmail` |
| Orphan A | `src/negotiation/audit/wiring.py` + `__init__.py` | all | Keep, wire, or explicitly remove | `tests/audit/test_wiring.py` | `TestCreateAuditedEmailReceive` |
| Orphan B | `src/negotiation/sheets/client.py` | 115-134 | Keep as utility, no action required | `tests/sheets/test_client.py` | existing tests |

---

## Open Questions

1. **ISSUE-02: What is the correct `proposed_cpm` value to pass to `pre_check`?**
   - What we know: `context.get("next_cpm")` holds the current negotiation CPM. This may be a `Decimal` while `pre_check` expects a `float`.
   - What's unclear: Does `SlackDispatcher.pre_check` accept `Decimal` or only `float`? Check `src/negotiation/slack/dispatcher.py` signature.
   - Recommendation: Read `dispatcher.py` `pre_check` signature before fixing ISSUE-02. If it expects `float`, use `float(context.get("next_cpm", Decimal("0")))`.

2. **ISSUE-02: What is the correct `intent_confidence` default?**
   - What we know: `1.0` was used as a placeholder, which may suppress intent-based escalation gates.
   - What's unclear: The correct value before intent classification is done (i.e., before `process_fn` runs). Should be `0.0` (no confidence yet) or should `intent_confidence` be omitted/defaulted in the dispatcher?
   - Recommendation: Read `pre_check` in `dispatcher.py` to understand what `intent_confidence` controls. Then choose the correct initial value.

3. **Orphan A: Connect `create_audited_email_receive` or delete exports?**
   - What we know: It is fully implemented, tested (2 tests in `test_wiring.py`), exported from `audit/__init__.py`, but never called from the pipeline.
   - What's unclear: Whether the MISSING-A fix should use it as a wrapper (connection approach) or bypass it with a direct `log_email_received()` call (the simpler approach documented in this research).
   - Recommendation: Use the direct call approach (simpler, already shown in Pattern 3). Keep the function and its tests — it's not harmful to have a tested utility that isn't in the hot path. Remove it from `__init__.py` exports only if the team wants minimal public surface.

---

## Sources

### Primary (HIGH confidence)

All findings from direct source code inspection — no external sources needed for this phase.

- `src/negotiation/campaign/ingestion.py` — ISSUE-01 bug location confirmed at lines 287, 323
- `src/negotiation/app.py` — ISSUE-02 confirmed at lines 655-656; MISSING-A gap confirmed (no `log_email_received` call in `process_inbound_email`)
- `src/negotiation/sheets/models.py` — ISSUE-03 confirmed: no `engagement_rate` field
- `src/negotiation/sheets/client.py` — `get_pay_range` exists but never called from `app.py` or `ingestion.py`
- `src/negotiation/audit/logger.py` — `log_email_received` method exists and is complete
- `src/negotiation/audit/wiring.py` — `create_audited_email_receive` exists, not wired
- `src/negotiation/campaign/cpm_tracker.py` — confirmed `get_flexibility(influencer_engagement_rate=None)` returns zero premium
- `src/negotiation/app.py` lines 340-365 — `build_negotiation_context` reads `getattr(sheet_data, "engagement_rate", None)`; once `InfluencerRow` has the field, real value flows through
- `tests/campaign/test_ingestion.py` — existing test patterns (anyio, MagicMock, fixtures)
- `tests/test_orchestration.py` — `_base_services` helper, `_make_mock_influencer_row` with `engagement_rate=4.5`
- `pyproject.toml` — pytest configuration, plugins (anyio-4.12.1, mock-3.15.1)
- `.venv/bin/python -m pytest` — confirmed 681 tests, all passing

---

## Metadata

**Confidence breakdown:**
- Bug locations: HIGH — confirmed by reading source files line by line
- Fix approaches: HIGH — patterns follow existing codebase conventions, no new libraries
- Test patterns: HIGH — copied from existing passing tests in same test files
- ISSUE-02 `intent_confidence` value: MEDIUM — semantics need verification against `dispatcher.py`

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (stable — internal codebase, not dependent on external library changes)
