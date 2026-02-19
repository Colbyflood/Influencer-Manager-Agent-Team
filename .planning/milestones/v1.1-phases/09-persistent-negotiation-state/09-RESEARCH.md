# Phase 9: Persistent Negotiation State - Research

**Researched:** 2026-02-19
**Domain:** SQLite state persistence, process crash recovery, in-memory/disk consistency
**Confidence:** HIGH

## Summary

Phase 9 persists the in-memory `negotiation_states` dict to SQLite so active negotiations survive process restarts. The codebase already uses raw `sqlite3.Connection` with WAL mode for the audit trail (no SQLAlchemy, no Alembic). The new `negotiation_state` table follows the exact same pattern: direct DDL in an `init_*` function, parameterized queries, WAL mode on the same database file.

The core challenge is serialization. The `negotiation_states` dict stores five fields per thread: a `NegotiationStateMachine` (enum state + history tuples), a `context` dict (plain JSON-serializable), a `round_count` int, a `Campaign` (frozen Pydantic model), and a `CampaignCPMTracker` (mutable class with `_agreements` list). The state machine and campaign are straightforward to serialize. The CPM tracker requires serializing its constructor args plus the `_agreements` list.

On startup, all non-terminal rows are loaded from SQLite, the `NegotiationStateMachine` is reconstructed with the saved state via its `initial_state` parameter, and the rest of the dict is rebuilt from stored JSON. The write-on-every-transition guarantee means the SQLite INSERT/UPDATE must happen synchronously inside the state transition path, before any email response is sent.

**Primary recommendation:** Add a `negotiation_state` table to the existing audit SQLite database using the same `init_audit_db()` DDL pattern. Create a `NegotiationStateStore` class (mirroring `AuditLogger`) that provides `save()`, `load_active()`, and `mark_terminal()` methods using parameterized queries. Hook `save()` into every code path that mutates `negotiation_states[thread_id]` -- the two sites are `start_negotiations_for_campaign` (initial creation) and `process_inbound_email` (state transitions + round_count increment).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STATE-01 | Agent persists negotiation state to SQLite on every state transition so no deals are lost on restart | New `negotiation_state` table with `save()` called after every `state_machine.trigger()` and `round_count` update. Uses same sqlite3.Connection + WAL pattern as audit trail. Write happens before email response is sent. See Architecture Patterns and Code Examples sections. |
| STATE-02 | Agent recovers non-terminal negotiations from database on startup so in-progress deals resume automatically | `load_active()` method queries `WHERE state NOT IN ('agreed', 'rejected')` on startup, reconstructs NegotiationStateMachine with `initial_state` parameter, deserializes context/campaign/cpm_tracker from JSON columns. Called in `initialize_services()` before app starts accepting requests. See Architecture Patterns and Code Examples sections. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | State persistence to SQLite | Already used for audit trail; zero new dependencies; same WAL-mode connection |
| json | stdlib | Serialize context dict, campaign model, CPM tracker to JSON columns | Pydantic models have `.model_dump_json()` / `model_validate_json()`; plain dicts use `json.dumps/loads` |
| pydantic | >=2.12,<3 | Campaign model serialization/deserialization | Already installed; `Campaign.model_dump_json()` and `Campaign.model_validate_json()` for lossless round-trip |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| structlog | >=25.5.0 | Logging state persistence operations | Already installed; log every save/load/recovery for observability |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw sqlite3 DDL | Alembic migrations | Alembic adds complexity (alembic.ini, env.py, migration scripts) for a single new table. The codebase has zero SQLAlchemy -- introducing it for one table is over-engineered. Follow existing audit trail pattern. |
| JSON columns for campaign/context | Normalized relational tables | Normalized schema requires joins and more complex queries for a single-reader/single-writer use case. JSON columns are simpler and the data is only read back by this same application. |
| SQLite | Redis | Prior decision: SQLite over Redis (zero new infrastructure). Redis would add a container, connection management, and a new failure mode. |
| Synchronous writes | Async/WAL-only writes | WAL mode already provides concurrent read/write. The write is fast (~1ms for a single row UPDATE) and must complete before the response to guarantee STATE-01. No need for async complexity. |

**Installation:**
```bash
# No new dependencies -- sqlite3 is stdlib, pydantic and structlog already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/negotiation/
├── state/                  # NEW: State persistence module
│   ├── __init__.py         # Exports NegotiationStateStore
│   ├── store.py            # NegotiationStateStore class (save, load_active, mark_terminal)
│   └── schema.py           # Table DDL and column definitions
├── audit/store.py          # EXISTING: Pattern to follow (init_audit_db, insert_audit_entry)
├── app.py                  # MODIFIED: Wire state store into initialize_services and process_inbound_email
└── config.py               # EXISTING: audit_db_path setting already covers the DB file
```

### Pattern 1: Negotiation State Table Schema
**What:** A single SQLite table storing one row per active negotiation, keyed by Gmail thread_id.
**When to use:** All state persistence operations (STATE-01, STATE-02).
**Schema:**
```sql
-- Source: Derived from codebase analysis of negotiation_states dict structure
CREATE TABLE IF NOT EXISTS negotiation_state (
    thread_id       TEXT PRIMARY KEY,
    state           TEXT NOT NULL,          -- NegotiationState enum value (e.g., 'awaiting_reply')
    round_count     INTEGER NOT NULL DEFAULT 0,
    context_json    TEXT NOT NULL,          -- JSON: the negotiation_context dict
    campaign_json   TEXT NOT NULL,          -- JSON: Campaign.model_dump_json()
    cpm_tracker_json TEXT NOT NULL,         -- JSON: CPMTracker serialized state
    history_json    TEXT NOT NULL DEFAULT '[]', -- JSON: state machine transition history
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_neg_state_state ON negotiation_state (state);
```

**Key design decisions:**
- `thread_id` as PRIMARY KEY (natural key, always unique, already used as dict key)
- `state` stored as plain TEXT (enum `.value`) for human-readable queries and debugging
- `context_json`, `campaign_json`, `cpm_tracker_json` as JSON TEXT columns (single-reader/single-writer app, no need for normalization)
- `history_json` stores the state machine transition history as JSON array of `[from_state, event, to_state]` triples
- `updated_at` updated on every write for debugging stale state
- Index on `state` for the startup recovery query (`WHERE state NOT IN (...)`)

### Pattern 2: NegotiationStateStore Class
**What:** A store class matching the `AuditLogger` pattern -- wraps a `sqlite3.Connection` and provides typed methods.
**When to use:** All read/write operations on negotiation state.
**Example:**
```python
# Source: Derived from audit/store.py and audit/logger.py patterns
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from negotiation.campaign.models import Campaign
from negotiation.domain.types import NegotiationState
from negotiation.state_machine import NegotiationStateMachine
from negotiation.state_machine.transitions import TERMINAL_STATES


class NegotiationStateStore:
    """SQLite-backed persistence for active negotiations."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(
        self,
        thread_id: str,
        state_machine: NegotiationStateMachine,
        context: dict[str, Any],
        campaign: Campaign,
        cpm_tracker_data: dict[str, Any],
        round_count: int,
    ) -> None:
        """Upsert negotiation state for a thread (INSERT OR REPLACE)."""
        now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        history = [
            [h[0].value, h[1], h[2].value] for h in state_machine.history
        ]
        self._conn.execute(
            """
            INSERT OR REPLACE INTO negotiation_state
                (thread_id, state, round_count, context_json, campaign_json,
                 cpm_tracker_json, history_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM negotiation_state WHERE thread_id = ?), ?),
                    ?)
            """,
            (
                thread_id,
                state_machine.state.value,
                round_count,
                json.dumps(context),
                campaign.model_dump_json(),
                json.dumps(cpm_tracker_data),
                json.dumps(history),
                thread_id,  # for COALESCE subquery
                now,        # fallback created_at for new rows
                now,        # updated_at
            ),
        )
        self._conn.commit()

    def load_active(self) -> list[dict[str, Any]]:
        """Load all non-terminal negotiations for startup recovery."""
        terminal_values = tuple(s.value for s in TERMINAL_STATES)
        placeholders = ",".join("?" for _ in terminal_values)
        cursor = self._conn.execute(
            f"SELECT * FROM negotiation_state WHERE state NOT IN ({placeholders})",
            terminal_values,
        )
        cursor.row_factory = sqlite3.Row
        return [dict(row) for row in cursor.fetchall()]

    def delete(self, thread_id: str) -> None:
        """Remove a negotiation state row (optional cleanup)."""
        self._conn.execute(
            "DELETE FROM negotiation_state WHERE thread_id = ?",
            (thread_id,),
        )
        self._conn.commit()
```

### Pattern 3: Serialization of Complex Objects
**What:** Converting the five fields of `negotiation_states[thread_id]` to/from SQLite-storable formats.
**When to use:** Every `save()` and `load_active()` call.

**Serialization map:**

| Object | Serialize | Deserialize |
|--------|-----------|-------------|
| `NegotiationStateMachine._state` | `sm.state.value` -> TEXT column `state` | `NegotiationStateMachine(initial_state=NegotiationState(state_text))` |
| `NegotiationStateMachine._history` | `[[h[0].value, h[1], h[2].value] for h in sm.history]` -> JSON | `[(NegotiationState(h[0]), h[1], NegotiationState(h[2])) for h in json.loads(history_json)]` |
| `context` dict | `json.dumps(context)` -> TEXT column | `json.loads(context_json)` |
| `Campaign` model | `campaign.model_dump_json()` -> TEXT column | `Campaign.model_validate_json(campaign_json)` |
| `CampaignCPMTracker` | Custom dict: `{"campaign_id": ..., "target_min_cpm": ..., "target_max_cpm": ..., "total_influencers": ..., "_agreements": [...]}` | Reconstruct: `CampaignCPMTracker(...)` then replay `_agreements` |
| `round_count` | Direct INTEGER column | Direct `int` |

**CampaignCPMTracker serialization detail:**
```python
def serialize_cpm_tracker(tracker: CampaignCPMTracker) -> dict[str, Any]:
    """Serialize CPMTracker to a JSON-safe dict."""
    return {
        "campaign_id": tracker.campaign_id,
        "target_min_cpm": str(tracker.target_min_cpm),
        "target_max_cpm": str(tracker.target_max_cpm),
        "total_influencers": tracker.total_influencers,
        "agreements": [
            {"cpm": str(cpm), "engagement_rate": er}
            for cpm, er in tracker._agreements
        ],
    }

def deserialize_cpm_tracker(data: dict[str, Any]) -> CampaignCPMTracker:
    """Reconstruct CPMTracker from serialized dict."""
    tracker = CampaignCPMTracker(
        campaign_id=data["campaign_id"],
        target_min_cpm=Decimal(data["target_min_cpm"]),
        target_max_cpm=Decimal(data["target_max_cpm"]),
        total_influencers=data["total_influencers"],
    )
    for agreement in data.get("agreements", []):
        tracker._agreements.append(
            (Decimal(agreement["cpm"]), agreement.get("engagement_rate"))
        )
    return tracker
```

**NegotiationStateMachine reconstruction:**
The state machine CANNOT simply be instantiated and replayed (triggering all historical events) because that would be fragile and slow. Instead, reconstruct it with the saved state directly:

```python
def reconstruct_state_machine(
    state_value: str,
    history_json: list[list[str]],
) -> NegotiationStateMachine:
    """Reconstruct a state machine from persisted data."""
    sm = NegotiationStateMachine(initial_state=NegotiationState(state_value))
    # Directly set _history (package-internal access, justified for persistence)
    sm._history = [
        (NegotiationState(h[0]), h[1], NegotiationState(h[2]))
        for h in history_json
    ]
    return sm
```

Note: This accesses the private `_history` attribute directly. This is acceptable because the persistence layer is tightly coupled to the state machine by design -- they are in the same package. An alternative is adding a `from_snapshot(state, history)` classmethod to `NegotiationStateMachine` for cleaner encapsulation.

### Pattern 4: Write-Before-Response Guarantee (STATE-01)
**What:** Every state mutation is persisted to SQLite before any response (email send, Slack notification) happens.
**When to use:** Both write sites in app.py.

**Write Site 1: `start_negotiations_for_campaign`** (app.py line 482)
```python
# Current code stores to in-memory dict:
negotiation_states[thread_id] = {
    "state_machine": state_machine,
    "context": context,
    "round_count": 0,
    "campaign": campaign,
    "cpm_tracker": cpm_tracker,
}

# ADD: Persist to SQLite immediately after
state_store.save(thread_id, state_machine, context, campaign,
                 serialize_cpm_tracker(cpm_tracker), 0)
```

**Write Site 2: `process_inbound_email`** (app.py line 698-738)
After the negotiation loop runs and before/after the email is sent:
```python
# After process_influencer_reply returns, the state_machine has been mutated.
# Save the new state BEFORE sending the email reply.
state_store.save(
    thread_id=inbound.thread_id,
    state_machine=state_machine,
    context=context,
    campaign=thread_state["campaign"],
    cpm_tracker_data=serialize_cpm_tracker(thread_state["cpm_tracker"]),
    round_count=thread_state["round_count"],
)

# THEN send the email
if result["action"] == "send":
    await asyncio.to_thread(gmail_client.send_reply, ...)
    thread_state["round_count"] += 1
    # Save again with updated round_count
    state_store.save(...)
```

### Pattern 5: Startup Recovery (STATE-02)
**What:** Load all non-terminal negotiations from SQLite on startup and populate `negotiation_states` dict.
**When to use:** In `initialize_services()`, after audit DB is initialized but before app starts.

```python
# In initialize_services(), after audit DB init:
state_store = NegotiationStateStore(audit_conn)
services["state_store"] = state_store

# Load persisted non-terminal negotiations
active_rows = state_store.load_active()
for row in active_rows:
    thread_id = row["thread_id"]
    state_machine = reconstruct_state_machine(
        row["state"], json.loads(row["history_json"])
    )
    context = json.loads(row["context_json"])
    campaign = Campaign.model_validate_json(row["campaign_json"])
    cpm_tracker = deserialize_cpm_tracker(json.loads(row["cpm_tracker_json"]))

    negotiation_states[thread_id] = {
        "state_machine": state_machine,
        "context": context,
        "round_count": row["round_count"],
        "campaign": campaign,
        "cpm_tracker": cpm_tracker,
    }

logger.info("Recovered negotiations from database", count=len(active_rows))
```

### Anti-Patterns to Avoid
- **Using Alembic for a single table addition:** The codebase uses raw DDL with `CREATE TABLE IF NOT EXISTS`. Adding Alembic requires SQLAlchemy, alembic.ini, env.py, and a migrations directory -- massive overhead for one table on a single-writer application. Follow the existing pattern.
- **Storing state machine as a pickle/binary blob:** Pickle is fragile across code changes, insecure, and not human-readable. JSON columns are debuggable with standard SQLite tools.
- **Replaying events to reconstruct state machine:** Don't call `trigger()` for each historical event on startup. This re-validates transitions (which should always pass) but is slow and could fail if the transition map ever changes. Directly set the state and history.
- **Async writes for state persistence:** The write must complete before the response for STATE-01's guarantee. Don't use background tasks or fire-and-forget patterns for state saves.
- **Separate database file for state:** Use the same `audit.db` (or rename to `negotiation.db`). The existing `audit_db_path` setting in `config.py` already points to the right file. One connection, one WAL mode setup.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pydantic model serialization | Custom dict-building for Campaign | `Campaign.model_dump_json()` / `Campaign.model_validate_json()` | Handles Decimal precision, frozen models, validators automatically; round-trip guaranteed |
| Schema migration framework | Alembic + SQLAlchemy | `CREATE TABLE IF NOT EXISTS` in init function | Existing pattern works; single-writer app; one new table |
| JSON serialization of Decimal | Custom encoder | `str(decimal_value)` in dict, `Decimal(str_value)` on load | Simple, lossless, human-readable |
| Thread-safe SQLite access | Custom locking | SQLite WAL mode + Connection-per-thread | WAL allows concurrent reads with writes; Python sqlite3 module handles threading |

**Key insight:** The existing audit trail already solved 90% of the persistence problem. The negotiation state store follows the exact same pattern -- same database, same DDL approach, same parameterized queries, same WAL mode. The only new complexity is serialization of domain objects.

## Common Pitfalls

### Pitfall 1: Decimal Precision Loss in JSON Round-Trip
**What goes wrong:** `json.dumps({"cpm": Decimal("20.50")})` raises `TypeError` because `json` doesn't handle `Decimal`. Using `float()` loses precision.
**Why it happens:** Python's `json` module doesn't know about `Decimal`. Converting to `float` introduces IEEE 754 approximation errors.
**How to avoid:** Always serialize Decimals as strings: `str(value)`. Deserialize with `Decimal(string)`. Pydantic's `model_dump_json()` handles this automatically for Pydantic models -- it serializes Decimal fields as strings.
**Warning signs:** Decimal values like `"20.50"` becoming `20.5` or `20.500000000000001` after a save/load cycle.

### Pitfall 2: INSERT OR REPLACE Resetting created_at
**What goes wrong:** `INSERT OR REPLACE` deletes the existing row and inserts a new one, losing the original `created_at` timestamp.
**Why it happens:** SQLite's `INSERT OR REPLACE` is semantically DELETE + INSERT, not UPDATE.
**How to avoid:** Use a COALESCE subquery for `created_at`:
```sql
COALESCE((SELECT created_at FROM negotiation_state WHERE thread_id = ?), ?)
```
Or use a separate INSERT for new rows and UPDATE for existing rows. The COALESCE approach is cleaner.
**Warning signs:** All rows having the same `created_at` as `updated_at` after any update.

### Pitfall 3: State Machine History Reconstruction with Private Attribute Access
**What goes wrong:** Directly setting `sm._history = [...]` works but is fragile if the state machine class changes its internals.
**Why it happens:** `NegotiationStateMachine` has no public API for setting history -- it only appends via `trigger()`.
**How to avoid:** Add a `@classmethod from_snapshot(cls, state, history)` to `NegotiationStateMachine` that constructs the machine with pre-populated state and history. This makes the persistence contract explicit.
**Warning signs:** Tests passing but a future refactor of the state machine breaking persistence silently.

### Pitfall 4: Missing Save on round_count Increment
**What goes wrong:** `process_inbound_email` increments `thread_state["round_count"]` AFTER sending the email. If the process crashes between send and save, the round count is wrong on recovery.
**Why it happens:** The current code does `thread_state["round_count"] += 1` after `gmail_client.send_reply`.
**How to avoid:** Save state with the incremented round_count immediately after `send_reply` returns, before any other processing. The save order should be: (1) save state with new machine state before send, (2) send email, (3) save again with incremented round_count. Or, pre-increment and save once before send.
**Warning signs:** After a crash recovery, a negotiation sends the same round's email twice.

### Pitfall 5: Forgetting to Save After Terminal State Transitions
**What goes wrong:** When the negotiation reaches AGREED or REJECTED (terminal), the state machine is updated but the row is never persisted. On restart, the negotiation appears active and the agent tries to resume it.
**Why it happens:** Terminal transitions happen inside `process_influencer_reply` (via `state_machine.trigger("accept")` or `trigger("reject")`), and the caller might skip the save because "the negotiation is over."
**How to avoid:** Always save after every `trigger()` call, including terminal transitions. The startup recovery query filters on `state NOT IN ('agreed', 'rejected')`, so terminal rows are harmlessly ignored. Alternatively, explicitly mark terminal rows or delete them.
**Warning signs:** Duplicate acceptance/rejection notifications after a restart.

### Pitfall 6: Campaign Model with Decimal Fields and JSON
**What goes wrong:** `Campaign.model_dump()` with default settings might serialize Decimal as float in some Pydantic versions.
**Why it happens:** Pydantic v2's `model_dump()` behavior for Decimal depends on `mode` parameter.
**How to avoid:** Use `Campaign.model_dump_json()` (returns JSON string) rather than `json.dumps(Campaign.model_dump())`. The `model_dump_json()` method uses Pydantic's JSON encoder which correctly handles Decimal as string. For loading, use `Campaign.model_validate_json(json_string)`.
**Warning signs:** `ValidationError` on load because float value rejected by `reject_float_inputs` validator.

## Code Examples

Verified patterns from the existing codebase:

### Table DDL Following Existing Audit Pattern
```python
# Source: Derived from src/negotiation/audit/store.py init_audit_db()
# File: src/negotiation/state/schema.py

def init_negotiation_state_table(conn: sqlite3.Connection) -> None:
    """Create the negotiation_state table if it does not exist.

    Called alongside init_audit_db() during startup. Uses the same
    connection and WAL mode already configured for the audit database.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS negotiation_state (
            thread_id       TEXT PRIMARY KEY,
            state           TEXT NOT NULL,
            round_count     INTEGER NOT NULL DEFAULT 0,
            context_json    TEXT NOT NULL,
            campaign_json   TEXT NOT NULL,
            cpm_tracker_json TEXT NOT NULL,
            history_json    TEXT NOT NULL DEFAULT '[]',
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_neg_state_state ON negotiation_state (state)"
    )
    conn.commit()
```

### Wiring into initialize_services()
```python
# Source: Derived from src/negotiation/app.py initialize_services()
# Shows where state store initialization and recovery fit

def initialize_services(settings: Settings | None = None) -> dict[str, Any]:
    # ... existing service initialization ...

    # a. Initialize SQLite audit database (EXISTING)
    audit_conn = init_audit_db(audit_db_path)

    # NEW: Initialize negotiation state table on same connection
    init_negotiation_state_table(audit_conn)

    # NEW: Create state store
    state_store = NegotiationStateStore(audit_conn)
    services["state_store"] = state_store

    # ... existing service initialization ...

    # j. In-memory negotiation state store (EXISTING)
    negotiation_states: dict[str, dict[str, Any]] = {}
    services["negotiation_states"] = negotiation_states

    # NEW: Recover non-terminal negotiations from database
    active_rows = state_store.load_active()
    for row in active_rows:
        thread_id = row["thread_id"]
        sm = reconstruct_state_machine(row["state"], json.loads(row["history_json"]))
        context = json.loads(row["context_json"])
        campaign = Campaign.model_validate_json(row["campaign_json"])
        cpm_tracker = deserialize_cpm_tracker(json.loads(row["cpm_tracker_json"]))

        negotiation_states[thread_id] = {
            "state_machine": sm,
            "context": context,
            "round_count": row["round_count"],
            "campaign": campaign,
            "cpm_tracker": cpm_tracker,
        }

    logger.info("Negotiation state recovery complete", recovered=len(active_rows))

    # ... rest of initialization ...
```

### Context Dict Serialization Handling
```python
# The context dict (from build_negotiation_context) contains mostly strings and ints.
# One field requires special handling:
# - "next_cpm" is a Decimal (from CampaignCPMRange or CPMFlexibility)
#
# json.dumps handles str, int, list[str] natively.
# Decimal must be converted to str before serialization.

def serialize_context(context: dict[str, Any]) -> str:
    """Serialize negotiation context to JSON, handling Decimal values."""
    serializable = {}
    for key, value in context.items():
        if isinstance(value, Decimal):
            serializable[key] = str(value)
        else:
            serializable[key] = value
    return json.dumps(serializable)

def deserialize_context(json_str: str) -> dict[str, Any]:
    """Deserialize negotiation context from JSON.

    Note: next_cpm comes back as string. The negotiation_loop accesses it
    as Decimal(str(context["next_cpm"])), so string is fine.
    """
    return json.loads(json_str)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Alembic for all schema changes | `CREATE TABLE IF NOT EXISTS` for single-writer apps | N/A (project convention) | No migration tooling needed; idempotent DDL on every startup |
| SQLAlchemy ORM for persistence | Raw sqlite3 with parameterized queries | N/A (project convention) | Simpler, fewer dependencies, direct control over SQL |
| Redis for ephemeral state | SQLite for durable state | v1.1 decision (2026-02-19) | Zero new infrastructure; same database as audit trail |

**Deprecated/outdated:**
- None. The approach uses stdlib sqlite3 and existing patterns. No deprecated APIs involved.

## Open Questions

1. **Whether to add `from_snapshot()` classmethod to NegotiationStateMachine**
   - What we know: Direct `_history` attribute access works but is fragile.
   - What's unclear: Whether the team prefers a clean public API vs. accepting internal access for persistence.
   - Recommendation: Add `from_snapshot(cls, state: NegotiationState, history: list[tuple])` classmethod. It's 5 lines of code and makes the persistence contract explicit. Tests for state machine reconstruction become cleaner.

2. **Whether to keep terminal-state rows or delete them**
   - What we know: The startup recovery query filters them out with `WHERE state NOT IN (...)`. Keeping them provides historical data. Deleting them keeps the table small.
   - What's unclear: Whether terminal state data has diagnostic value beyond the audit trail (which already logs agreements and rejections).
   - Recommendation: Keep terminal rows (never delete). Storage cost is negligible. They provide a denormalized view of negotiation outcomes that complements the audit log. Add a `completed_at` column that gets set when state becomes terminal for easy querying.

3. **Whether to use `asyncio.to_thread` for SQLite writes in async context**
   - What we know: `process_inbound_email` is async. The audit trail's `insert_audit_entry` does synchronous writes without `to_thread`. SQLite writes with WAL mode take ~1ms.
   - What's unclear: Whether the ~1ms blocking write is acceptable in the async event loop.
   - Recommendation: Follow the existing audit pattern -- synchronous writes without `to_thread`. The write is fast (~1ms), and adding `to_thread` would complicate the write-before-response guarantee. The audit trail has been running this way successfully.

4. **How to handle the CampaignCPMTracker `_agreements` private attribute**
   - What we know: `_agreements` is a list of `(Decimal, float | None)` tuples. Accessing it for serialization works but is accessing a private attribute.
   - What's unclear: Whether to add a public `agreements` property or serialization methods to `CampaignCPMTracker`.
   - Recommendation: Add a `to_dict()` / `from_dict()` classmethod pair to `CampaignCPMTracker`. This is cleaner than external serialization functions accessing private state. Alternatively, a read-only `agreements` property.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `src/negotiation/audit/store.py` -- existing SQLite persistence pattern with WAL mode, parameterized queries, and DDL-on-startup
- Codebase analysis: `src/negotiation/state_machine/machine.py` -- NegotiationStateMachine class fields (`_state`, `_history`), constructor accepts `initial_state`
- Codebase analysis: `src/negotiation/app.py` -- `negotiation_states` dict structure (lines 482-488), both write sites (start_negotiations, process_inbound_email)
- Codebase analysis: `src/negotiation/campaign/models.py` -- Campaign frozen Pydantic model with Decimal fields and `reject_float_inputs` validators
- Codebase analysis: `src/negotiation/campaign/cpm_tracker.py` -- CampaignCPMTracker mutable class with `_agreements` list
- Codebase analysis: `src/negotiation/config.py` -- `audit_db_path` setting already configured
- Python sqlite3 docs: WAL mode, `INSERT OR REPLACE`, parameterized queries

### Secondary (MEDIUM confidence)
- Pydantic v2 docs: `model_dump_json()` / `model_validate_json()` for lossless Decimal serialization
- Prior Phase 8 research: `08-RESEARCH.md` -- confirmed pattern of Settings on services dict and app.state

### Tertiary (LOW confidence)
- None -- all findings derived from direct codebase analysis and stdlib documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses only stdlib (sqlite3, json) and existing dependencies (pydantic). No new packages needed.
- Architecture: HIGH - Pattern directly follows existing audit trail implementation. All write sites identified by code analysis.
- Pitfalls: HIGH - Decimal serialization, INSERT OR REPLACE behavior, and private attribute access are verified from codebase inspection.
- Serialization design: HIGH - Every field of `negotiation_states[thread_id]` analyzed with concrete serialize/deserialize strategies.

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable pattern; no external dependencies to change)
