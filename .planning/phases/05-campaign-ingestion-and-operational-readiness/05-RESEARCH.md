# Phase 5: Campaign Ingestion and Operational Readiness - Research

**Researched:** 2026-02-19
**Domain:** ClickUp webhook integration, SQLite audit trail, campaign-to-negotiation mapping, retry/error handling, production hardening
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### ClickUp Campaign Ingestion
- ClickUp webhook integration (real-time, not polling)
- Standard field set: client name, budget, target deliverables, influencer list, CPM range, platform, timeline
- One campaign can cover many influencers -- a single submission lists multiple influencers, agent starts negotiations with all of them
- Auto-start negotiations on webhook receipt -- agent immediately begins outreach, team gets a Slack notification that it started
- One-way data flow only: ClickUp -> agent (no status sync back to ClickUp)

#### Conversation Audit Trail
- SQLite database for storage -- queryable with SQL, zero infrastructure, easy to back up
- Full context per entry: timestamp, direction (sent/received), email body, negotiation state, rates used, intent classification, campaign ID, influencer name
- Log everything: emails, escalations, takeovers, campaign starts, state transitions, agreement closures
- Both CLI and Slack query interfaces: CLI for detailed queries (by influencer, campaign, date range), Slack commands for quick lookups

#### Campaign-to-Negotiation Mapping
- Campaign-level CPM target range applies to all influencers as default
- Dynamic adjustment: agent tracks running campaign average CPM and adjusts flexibility for remaining influencers to hit overall target
- Flexibility considers engagement quality -- not just raw CPM. Agent factors in follower engagement rate to determine if going past target CPM provides benefit by reaching a highly engaged audience. The agent should not decide on campaign CPM averaging alone
- Missing influencers (not in Google Sheet): skip and post Slack alert asking team to add them first

#### Production Hardening
- Retry then escalate on API failures: retry 3 times with backoff, then post error to Slack #errors channel for team visibility
- Applies to all external APIs: Gmail, Slack, ClickUp, Anthropic

### Claude's Discretion
- Runtime model (long-running process vs event-driven)
- Config management approach (env vars, config files, or hybrid)
- Logging format (structured JSON vs console)
- Exact retry backoff strategy and timing
- SQLite schema design
- Slack audit query response formatting

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Agent accepts campaign data from ClickUp form submissions to understand the specific deliverables, goals, channels needed, and other key details to guide decision making for negotiations | ClickUp form submissions create tasks in a designated list. Subscribe to `taskCreated` webhook event on that list. Parse task custom fields (client name, budget, deliverables, influencer list, CPM range, platform, timeline) from the webhook payload. FastAPI webhook receiver with HMAC-SHA256 signature verification. See [ClickUp Webhook Integration](#pattern-1-clickup-webhook-receiver) and [Campaign Model](#pattern-2-campaign-data-model). |
| DATA-03 | Agent logs every sent/received email with timestamps, negotiation state, and rates used | SQLite audit trail with `audit_log` table storing timestamp, direction, email body, negotiation state, rates, intent classification, campaign ID, influencer name. Insert calls wired into the existing `process_influencer_reply` loop and `GmailClient.send`/`send_reply` methods. See [SQLite Audit Trail](#pattern-3-sqlite-audit-trail) and [Schema Design](#sqlite-schema-design-recommendation). |
| DATA-04 | Agent maintains queryable conversation audit trail by influencer, campaign, or date range | SQLite indexed queries by influencer_name, campaign_id, and timestamp columns. CLI interface using argparse for detailed SQL queries. Slack slash commands (`/audit`) for quick lookups with Block Kit formatted responses. See [Query Interfaces](#pattern-5-audit-query-interfaces). |
</phase_requirements>

## Summary

Phase 5 connects the existing negotiation pipeline (Phases 1-4) to external campaign data from ClickUp and adds full operational visibility through a conversation audit trail. The phase has three major components: (1) a webhook receiver that ingests campaign data from ClickUp form submissions and automatically starts negotiations with all listed influencers, (2) a SQLite-backed audit trail that logs every negotiation action with full context, queryable via CLI and Slack, and (3) production hardening with retry logic and error escalation across all external API calls.

The ClickUp integration works through the form-to-task-to-webhook pipeline: when a team member submits a ClickUp form, ClickUp creates a task in a designated list with custom fields mapped from the form. Our agent subscribes to the `taskCreated` webhook event on that list. When fired, the webhook delivers a POST request with the task payload including custom field values. The agent parses the campaign data, looks up each influencer in the Google Sheet, and starts negotiations for all found influencers while alerting on any missing ones. This requires a lightweight HTTP server -- FastAPI is the recommended choice since the existing Slack Bolt app already uses Socket Mode (WebSocket) and does not provide an HTTP endpoint.

The audit trail uses Python's stdlib `sqlite3` module with WAL (Write-Ahead Logging) mode for concurrent read/write access. Every action in the system -- emails sent/received, escalations, takeovers, campaign starts, state transitions, agreement closures -- gets logged with full context. The CLI query interface uses argparse for filtering by influencer, campaign, or date range. Slack queries use a new `/audit` slash command registered on the existing Bolt app, returning Block Kit formatted results.

Production hardening wraps all external API calls (Gmail, Slack, ClickUp, Anthropic) with the `tenacity` retry library using exponential backoff with jitter (3 attempts, then Slack error notification). This is a cross-cutting concern applied via decorators or wrapper functions.

**Primary recommendation:** Use FastAPI with uvicorn for the webhook receiver, Python stdlib `sqlite3` with WAL mode for the audit trail, `tenacity` for retry logic, and `structlog` for structured JSON logging. Run as a long-running process that combines the FastAPI webhook server and the existing Slack Bolt Socket Mode handler.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | >=0.115.0 | HTTP server for receiving ClickUp webhooks | Async, lightweight, automatic request validation with Pydantic, built-in OpenAPI docs. Standard choice for Python webhook receivers. |
| `uvicorn` | >=0.34.0 | ASGI server to run FastAPI | Standard production ASGI server for FastAPI; supports `--workers` for multi-process deployment. |
| `tenacity` | >=9.0.0 | Retry logic with exponential backoff for all external API calls | De facto standard Python retry library; decorator-based, supports exponential backoff with jitter, `stop_after_attempt`, custom callbacks. |
| `structlog` | >=25.0.0 | Structured JSON logging for production observability | Standard Python structured logging; JSON output in production, human-readable in development; contextual binding (campaign_id, influencer_name). |
| `sqlite3` | stdlib | Audit trail database | Zero-dependency, zero-infrastructure; WAL mode for concurrent access; SQL queryable; easy backup (single file). Already in Python stdlib. |
| `pydantic` | >=2.12,<3 | Campaign data models, webhook payload validation | Already in project; validates ClickUp webhook payloads against schema. |
| `anthropic` | >=0.82.0 | LLM client for negotiation (existing) | Already in project. |
| `slack-sdk` | >=3.40.1 | Slack notifications (existing) | Already in project. |
| `slack-bolt` | >=1.27.0 | Slack slash commands for audit queries (existing) | Already in project. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | >=0.28.0 | HTTP client for ClickUp API calls (fetching task details if needed) | Only needed if webhook payload does not include all custom fields and a follow-up GET to ClickUp API is required. |
| `pytest` | >=9.0,<10 | Testing | Already in project dev dependencies. |
| `pytest-mock` | >=3.15.1 | Mocking external APIs in tests | Already in project dev dependencies. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask | Flask is synchronous by default. FastAPI is async-native, which matters for webhook processing where we do not want to block on downstream API calls (Sheets lookup, Gmail send). FastAPI also has built-in Pydantic integration for request validation. |
| FastAPI | aiohttp | Lower-level, more manual setup. FastAPI provides automatic request parsing, validation, and OpenAPI docs with less code. |
| `sqlite3` stdlib | `aiosqlite` | `aiosqlite` provides async access but adds dependency. Since SQLite writes are fast (sub-millisecond for single inserts) and we use WAL mode, synchronous `sqlite3` in a thread pool is sufficient for this workload. |
| `tenacity` | Custom retry logic | Tenacity handles edge cases (jitter, callback hooks, exception filtering, async support) that hand-rolled retry loops miss. Well-tested, zero learning curve with decorator syntax. |
| `structlog` | stdlib `logging` with JSON formatter | stdlib logging requires manual JSON formatting and lacks contextual binding. structlog provides these out of the box. The overhead of adding one dependency is worth the cleaner logging code. |

**Installation:**
```bash
uv add fastapi uvicorn tenacity structlog
```

Note: `sqlite3`, `argparse`, and `hmac` are Python stdlib -- no installation needed.

## Architecture Patterns

### Recommended Project Structure
```
src/negotiation/
├── domain/          # Existing: types, models, errors
├── pricing/         # Existing: CPM engine, rate cards, boundaries
├── email/           # Existing: Gmail client, parser, threading
├── sheets/          # Existing: Google Sheets client, models
├── llm/             # Existing: Anthropic client, intent, composer, negotiation loop
├── slack/           # Existing: notifier, commands, triggers, dispatcher, takeover
├── state_machine/   # Existing: states, transitions
├── auth/            # Existing: credentials
├── campaign/        # NEW: Campaign ingestion
│   ├── __init__.py
│   ├── models.py         # Campaign, CampaignInfluencer Pydantic models
│   ├── webhook.py        # FastAPI webhook endpoint + signature verification
│   ├── ingestion.py      # Campaign processing: parse -> lookup -> start negotiations
│   └── cpm_tracker.py    # Running campaign CPM average + engagement-quality logic
├── audit/           # NEW: Conversation audit trail
│   ├── __init__.py
│   ├── models.py         # AuditEntry Pydantic model, EventType enum
│   ├── store.py          # SQLite database operations (init, insert, query)
│   ├── cli.py            # CLI query interface (argparse)
│   └── slack_commands.py # Slack /audit command handler
├── resilience/      # NEW: Retry and error handling
│   ├── __init__.py
│   └── retry.py          # Tenacity decorators, Slack error notification
└── app.py           # NEW: Application entry point (combines FastAPI + Slack Bolt)
```

### Pattern 1: ClickUp Webhook Receiver

**What:** FastAPI endpoint that receives ClickUp webhook POST requests, verifies the HMAC-SHA256 signature, validates the payload, and triggers campaign ingestion.

**When to use:** Every time a ClickUp form is submitted and a task is created in the monitored list.

**How ClickUp forms work:** When a team member submits a ClickUp form, ClickUp automatically creates a task in a designated list. Form fields map to task custom fields. The agent subscribes to `taskCreated` webhook events on that list. When a task is created (whether by form or manually), ClickUp sends a POST request to our endpoint with the task_id in the payload. The full task details including custom fields may need to be fetched via a follow-up GET to `https://api.clickup.com/api/v2/task/{task_id}?include_subtasks=true&custom_task_ids=false`.

**Security:** ClickUp signs webhooks using HMAC-SHA256. The signature is in the `X-Signature` header. Verify by computing `hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()` and comparing with `hmac.compare_digest()`.

**Example:**
```python
# Source: ClickUp webhook signature docs + FastAPI patterns
import hashlib
import hmac
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

CLICKUP_WEBHOOK_SECRET = os.environ["CLICKUP_WEBHOOK_SECRET"]

@app.post("/webhooks/clickup")
async def handle_clickup_webhook(request: Request) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    expected = hmac.new(
        CLICKUP_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")

    if event == "taskCreated":
        task_id = payload["task_id"]
        # Fetch full task with custom fields from ClickUp API
        # Parse into Campaign model
        # Start negotiations for each influencer
        await process_campaign_task(task_id)

    return {"status": "ok"}
```

**Important ClickUp webhook notes:**
- Webhook payloads for `taskCreated` contain `event`, `task_id`, `webhook_id`, and `history_items` but may NOT include custom field values directly.
- A follow-up GET request to `https://api.clickup.com/api/v2/task/{task_id}` is typically needed to retrieve the full task with custom fields. This is a well-documented pattern in the ClickUp ecosystem.
- Custom field values are NOT normalized -- cast to the correct type as needed (numbers may be strings, dates are Unix milliseconds).
- ClickUp rate limit: 100 requests/minute per token.
- The webhook secret is returned when the webhook is created via the ClickUp API and must be stored securely.

### Pattern 2: Campaign Data Model

**What:** Pydantic models representing campaign data ingested from ClickUp, bridging the external format to internal domain types.

**When to use:** After parsing the ClickUp task payload, before starting negotiations.

**Example:**
```python
# Campaign data model aligned with locked field set
from decimal import Decimal
from pydantic import BaseModel, Field
from negotiation.domain.types import Platform


class CampaignInfluencer(BaseModel):
    """A single influencer within a campaign."""
    name: str
    platform: Platform
    # engagement_rate stored for quality-weighted CPM decisions
    engagement_rate: float | None = None


class CampaignCPMRange(BaseModel):
    """CPM target range for a campaign."""
    min_cpm: Decimal
    max_cpm: Decimal


class Campaign(BaseModel):
    """Campaign data ingested from ClickUp form submission."""
    campaign_id: str = Field(description="ClickUp task ID as campaign identifier")
    client_name: str
    budget: Decimal
    target_deliverables: str
    influencers: list[CampaignInfluencer]
    cpm_range: CampaignCPMRange
    platform: Platform
    timeline: str
    created_at: str  # ISO 8601 timestamp
```

### Pattern 3: SQLite Audit Trail

**What:** A SQLite database with WAL mode that logs every negotiation action with full context, queryable by influencer, campaign, or date range.

**When to use:** On every action in the negotiation pipeline -- email sent/received, state transition, escalation, takeover, campaign start, agreement.

**Example:**
```python
# Source: Python sqlite3 stdlib + WAL mode best practices
import sqlite3
from pathlib import Path

def init_audit_db(db_path: Path) -> sqlite3.Connection:
    """Initialize the audit database with WAL mode and schema."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
            event_type TEXT NOT NULL,
            campaign_id TEXT,
            influencer_name TEXT,
            thread_id TEXT,
            direction TEXT,
            email_body TEXT,
            negotiation_state TEXT,
            rates_used TEXT,
            intent_classification TEXT,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_influencer
        ON audit_log(influencer_name)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_campaign
        ON audit_log(campaign_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp
        ON audit_log(timestamp)
    """)
    conn.commit()
    return conn
```

### Pattern 4: Campaign CPM Tracker with Engagement Quality

**What:** Tracks running average CPM across a campaign and adjusts negotiation flexibility for remaining influencers, factoring in engagement quality.

**When to use:** Before each negotiation round, to determine CPM flexibility for the current influencer.

**Key design insight:** The user explicitly decided that CPM flexibility should NOT be based on campaign averaging alone. The agent must factor in follower engagement rate to determine if going past target CPM provides benefit. A highly engaged influencer at slightly above-target CPM may be worth more than a low-engagement influencer under target.

**Example:**
```python
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class CPMFlexibility:
    """Result of CPM flexibility calculation for a specific influencer."""
    target_cpm: Decimal
    max_allowed_cpm: Decimal
    reason: str


class CampaignCPMTracker:
    """Tracks running campaign CPM average and calculates per-influencer flexibility."""

    def __init__(
        self,
        campaign_id: str,
        target_min_cpm: Decimal,
        target_max_cpm: Decimal,
        total_influencers: int,
    ) -> None:
        self._campaign_id = campaign_id
        self._target_min = target_min_cpm
        self._target_max = target_max_cpm
        self._total = total_influencers
        self._agreed: list[tuple[Decimal, float | None]] = []  # (cpm, engagement_rate)

    def record_agreement(self, cpm: Decimal, engagement_rate: float | None = None) -> None:
        """Record an agreed CPM for the campaign."""
        self._agreed.append((cpm, engagement_rate))

    @property
    def running_average_cpm(self) -> Decimal | None:
        if not self._agreed:
            return None
        return sum(cpm for cpm, _ in self._agreed) / len(self._agreed)

    def get_flexibility(
        self,
        influencer_engagement_rate: float | None,
    ) -> CPMFlexibility:
        """Calculate CPM flexibility for the next influencer.

        Considers both campaign average tracking AND engagement quality.
        High-engagement influencers get more CPM headroom.
        """
        remaining = self._total - len(self._agreed)
        if remaining <= 0:
            return CPMFlexibility(
                target_cpm=self._target_max,
                max_allowed_cpm=self._target_max,
                reason="All influencers already agreed",
            )

        base_target = self._target_max  # Start at campaign max

        # Adjust based on running average (campaign-level pressure)
        avg = self.running_average_cpm
        if avg is not None:
            headroom = self._target_max - avg
            # If running below target, allow more flexibility
            # If running above target, tighten
            base_target = self._target_max + (headroom * Decimal("0.5"))

        # Engagement quality adjustment
        # High engagement (>5%) gets up to 15% CPM premium
        engagement_premium = Decimal("1.0")
        if influencer_engagement_rate and influencer_engagement_rate > 0.05:
            engagement_premium = Decimal("1.15")
        elif influencer_engagement_rate and influencer_engagement_rate > 0.03:
            engagement_premium = Decimal("1.08")

        max_allowed = min(
            base_target * engagement_premium,
            self._target_max * Decimal("1.20"),  # Hard cap: never exceed 120% of target max
        )

        return CPMFlexibility(
            target_cpm=base_target,
            max_allowed_cpm=max_allowed,
            reason=self._build_reason(avg, influencer_engagement_rate, engagement_premium),
        )
```

### Pattern 5: Audit Query Interfaces

**What:** CLI and Slack interfaces for querying the audit trail.

**When to use:** CLI for detailed investigation, Slack for quick team lookups.

**CLI Example:**
```python
# CLI: python -m negotiation.audit.cli --influencer "Jane Doe" --last 7d
# CLI: python -m negotiation.audit.cli --campaign "camp_123" --from 2026-02-01
import argparse

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query negotiation audit trail")
    parser.add_argument("--influencer", help="Filter by influencer name")
    parser.add_argument("--campaign", help="Filter by campaign ID")
    parser.add_argument("--from-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--event-type", help="Filter by event type")
    parser.add_argument("--last", help="Shorthand: 7d, 24h, 30d")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    return parser
```

**Slack Command Example:**
```python
# /audit influencer:Jane Doe last:7d
# /audit campaign:camp_123
@app.command("/audit")
def handle_audit(ack, command, respond):
    ack()
    query_text = command.get("text", "").strip()
    # Parse query parameters from text
    results = query_audit_trail(parse_audit_query(query_text))
    blocks = format_audit_blocks(results)
    respond(blocks=blocks)
```

### Pattern 6: Resilience Wrapper with Tenacity

**What:** Retry decorators for all external API calls with exponential backoff, jitter, and Slack error notification on final failure.

**When to use:** Applied to every function that calls Gmail, Slack, ClickUp, or Anthropic APIs.

**Example:**
```python
# Source: tenacity docs + locked decision (3 retries, then Slack escalate)
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

logger = structlog.get_logger()

def create_api_retry(api_name: str):
    """Create a retry decorator for a specific API."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )

# Usage:
@create_api_retry("gmail")
def send_email(client, outbound):
    return client.send(outbound)
```

### Pattern 7: Application Entry Point

**What:** Single entry point that runs both the FastAPI webhook server and the Slack Bolt Socket Mode handler concurrently.

**When to use:** Production startup.

**Recommendation (Claude's Discretion -- Runtime Model):** Use a **long-running process** model. Run FastAPI (uvicorn) for webhook reception and Slack Bolt Socket Mode handler in the same process using `asyncio`. The FastAPI server handles ClickUp webhooks on an HTTP port. The Slack Bolt handler maintains a WebSocket connection for slash commands. Both share access to the SQLite audit database and the campaign/negotiation state.

Rationale: Event-driven (serverless/Lambda) is inappropriate because (a) the Slack Bolt Socket Mode handler needs a persistent WebSocket connection, (b) SQLite requires local filesystem access, and (c) the agent maintains in-memory state (ThreadStateManager). A long-running process is the simplest model that supports all these requirements.

**Example:**
```python
import asyncio
import uvicorn
from negotiation.campaign.webhook import app as fastapi_app
from negotiation.slack.app import create_slack_app, start_slack_app

async def main():
    # Start FastAPI in background
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)

    # Start Slack Bolt Socket Mode in background thread
    slack_app = create_slack_app()
    # Register audit commands, campaign notification handlers

    # Run both concurrently
    await asyncio.gather(
        server.serve(),
        # Slack Bolt runs in a thread since it uses synchronous SDK
    )
```

### Anti-Patterns to Avoid
- **Polling ClickUp API for new tasks:** Wastes API quota (100 req/min limit), adds latency. User explicitly chose webhooks.
- **Writing custom retry loops:** Misses edge cases (jitter, async support, exception filtering). Use tenacity.
- **Storing audit data in flat files (JSON/CSV):** Not queryable with SQL, no indexing, no concurrent access guarantees. User chose SQLite.
- **Parsing webhook body as JSON before signature verification:** Stringifying parsed JSON may add/remove whitespace, breaking the HMAC. Always verify against the raw body bytes.
- **Using a single SQLite connection across threads:** SQLite connections are not thread-safe. Use a connection-per-thread pattern or a connection pool.
- **Syncing status back to ClickUp:** User explicitly scoped this as one-way (ClickUp -> agent only).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with backoff | Custom while-loop with sleep | `tenacity` library | Handles jitter, exponential backoff, exception filtering, async support, callback hooks. Hand-rolled retries miss edge cases and are hard to test. |
| Webhook signature verification | Custom HMAC implementation | `hmac.compare_digest()` from stdlib | Timing-safe comparison prevents timing attacks. Never use `==` for signature comparison. |
| Structured logging | Custom JSON formatting | `structlog` | Contextual binding, processor pipeline, development/production mode switching. |
| HTTP server for webhooks | Custom socket handler | `FastAPI` + `uvicorn` | Automatic request parsing, Pydantic validation, async support, production-grade ASGI server. |
| SQL query builder | String concatenation | Parameterized queries (`?` placeholders) | SQL injection prevention. Always use `cursor.execute("SELECT ... WHERE name = ?", (name,))`. |

**Key insight:** This phase adds four external integration points (ClickUp webhooks, SQLite, retry logic, structured logging). Each has well-established Python libraries that handle edge cases. The complexity is in the orchestration -- wiring these together with the existing Phases 1-4 code -- not in the individual components.

## Common Pitfalls

### Pitfall 1: ClickUp Webhook Payload Missing Custom Fields
**What goes wrong:** The `taskCreated` webhook payload contains `task_id`, `event`, and `history_items` but may NOT include the full task object with custom field values. Developers assume the payload contains everything and fail to parse campaign data.
**Why it happens:** ClickUp webhook payloads are optimized for notification (what changed) not for data delivery (full object). Custom field values are often absent from the webhook payload itself.
**How to avoid:** Always follow up the webhook notification with a GET request to `https://api.clickup.com/api/v2/task/{task_id}` using the ClickUp API token. Include this as a required step in campaign ingestion, not as a fallback.
**Warning signs:** Campaign model fields coming back as None/empty despite the form being filled out correctly.

### Pitfall 2: SQLite Connection Thread Safety
**What goes wrong:** Sharing a single `sqlite3.Connection` across threads causes `ProgrammingError` or corrupted data.
**Why it happens:** Python's sqlite3 module uses `check_same_thread=True` by default for safety.
**How to avoid:** Either create connections per-thread, or use `check_same_thread=False` with proper external locking (a threading.Lock around write operations). Since FastAPI is async, audit writes from the webhook handler should go through a dedicated thread or use `asyncio.to_thread()`.
**Warning signs:** Intermittent `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` errors under concurrent load.

### Pitfall 3: ClickUp Custom Field Type Casting
**What goes wrong:** Custom field values from ClickUp are not normalized. Numbers may come as strings, dates as Unix milliseconds (integers), dropdowns as option IDs instead of labels.
**Why it happens:** ClickUp's API returns custom fields with type-dependent value formats. The `type_config` object describes the format but the `value` needs manual casting.
**How to avoid:** Build a field-type-aware parser that handles each custom field type explicitly. Use Pydantic validators with `mode="before"` to coerce values (similar to how `InfluencerRow.coerce_from_sheet_float` handles Google Sheets floats).
**Warning signs:** Validation errors on campaign model construction, especially for budget (currency field) and timeline (date field).

### Pitfall 4: Webhook Signature Verification with Parsed JSON
**What goes wrong:** The HMAC signature is computed over the raw request body bytes. If the framework parses the body as JSON first, then the developer re-serializes it for verification, whitespace differences cause the signature to not match.
**How to avoid:** Always verify the signature using the raw request body (`await request.body()`) BEFORE parsing as JSON. In FastAPI, use `Request` directly instead of a Pydantic model parameter for the webhook endpoint.
**Warning signs:** All webhook requests fail signature verification despite correct secret.

### Pitfall 5: SQLite Audit Insert Blocking the Request Loop
**What goes wrong:** Synchronous SQLite inserts in the async FastAPI request handler block the event loop, causing webhook response timeouts.
**Why it happens:** `sqlite3` is synchronous. Calling `conn.execute()` directly in an `async def` handler blocks the entire asyncio event loop.
**How to avoid:** Use `asyncio.to_thread()` to run SQLite operations in a thread pool, or use a background task queue for audit writes.
**Warning signs:** ClickUp webhook delivery starts failing because the endpoint does not respond within the timeout window.

### Pitfall 6: Campaign CPM Averaging Without Engagement Quality
**What goes wrong:** The agent only uses running campaign average CPM to adjust flexibility, treating all influencers as interchangeable. A high-engagement influencer at slightly above target gets the same treatment as a low-engagement one.
**Why it happens:** Simple arithmetic averaging ignores the user's explicit requirement that engagement quality must factor into CPM decisions.
**How to avoid:** Always include engagement rate in the CPM flexibility calculation. Build the engagement quality weighting into the `CampaignCPMTracker` from the start, not as an afterthought.
**Warning signs:** Team seeing the agent reject high-quality influencers solely because the campaign average is running hot.

## Code Examples

Verified patterns from official sources and the existing codebase:

### ClickUp Webhook Registration (one-time setup)
```python
# Source: ClickUp API docs - Create Webhook endpoint
# This is a one-time setup call, not part of the running application
import requests

def register_clickup_webhook(
    team_id: str,
    api_token: str,
    endpoint_url: str,
    list_id: str,
) -> dict:
    """Register a ClickUp webhook for task creation events on a list.

    Returns the webhook details including the secret for signature verification.
    Store the secret securely (environment variable).
    """
    response = requests.post(
        f"https://api.clickup.com/api/v2/team/{team_id}/webhook",
        headers={"Authorization": api_token},
        json={
            "endpoint": endpoint_url,
            "events": ["taskCreated"],
            "space_id": None,
            "folder_id": None,
            "list_id": list_id,
            "task_id": None,
        },
    )
    response.raise_for_status()
    result = response.json()
    # result["webhook"]["secret"] contains the HMAC secret
    return result
```

### Fetching Task Custom Fields from ClickUp API
```python
# Source: ClickUp API docs - Get Task endpoint
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=15))
async def fetch_clickup_task(task_id: str, api_token: str) -> dict:
    """Fetch full task details including custom fields from ClickUp."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.clickup.com/api/v2/task/{task_id}",
            headers={"Authorization": api_token},
        )
        response.raise_for_status()
        return response.json()


def parse_custom_fields(task_data: dict, field_mapping: dict[str, str]) -> dict:
    """Extract custom field values from a ClickUp task.

    Args:
        task_data: Full task response from ClickUp API.
        field_mapping: Maps custom field names to campaign model field names.
            e.g. {"Client Name": "client_name", "Budget": "budget"}

    Returns:
        Dict of campaign field name -> value.
    """
    custom_fields = task_data.get("custom_fields", [])
    result = {}
    for field in custom_fields:
        field_name = field.get("name", "")
        if field_name in field_mapping:
            result[field_mapping[field_name]] = field.get("value")
    return result
```

### SQLite Audit Trail Insert (follows existing Pydantic pattern)
```python
# Follows the project's Pydantic model pattern (frozen models, StrEnum)
import json
import sqlite3
from enum import StrEnum
from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Types of events logged in the audit trail."""
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    STATE_TRANSITION = "state_transition"
    ESCALATION = "escalation"
    AGREEMENT = "agreement"
    TAKEOVER = "takeover"
    CAMPAIGN_START = "campaign_start"
    CAMPAIGN_INFLUENCER_SKIP = "campaign_influencer_skip"
    ERROR = "error"


class AuditEntry(BaseModel):
    """A single audit trail entry."""
    event_type: EventType
    campaign_id: str | None = None
    influencer_name: str | None = None
    thread_id: str | None = None
    direction: str | None = None  # "sent" or "received"
    email_body: str | None = None
    negotiation_state: str | None = None
    rates_used: str | None = None  # JSON string of rate data
    intent_classification: str | None = None
    metadata: dict | None = None  # Flexible additional context


def insert_audit_entry(conn: sqlite3.Connection, entry: AuditEntry) -> int:
    """Insert an audit entry and return the row ID."""
    cursor = conn.execute(
        """INSERT INTO audit_log
           (event_type, campaign_id, influencer_name, thread_id,
            direction, email_body, negotiation_state, rates_used,
            intent_classification, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.event_type,
            entry.campaign_id,
            entry.influencer_name,
            entry.thread_id,
            entry.direction,
            entry.email_body,
            entry.negotiation_state,
            entry.rates_used,
            entry.intent_classification,
            json.dumps(entry.metadata) if entry.metadata else None,
        ),
    )
    conn.commit()
    return cursor.lastrowid or 0
```

### Tenacity Retry with Slack Error Notification
```python
# Follows locked decision: retry 3x with backoff, then post to Slack #errors
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, RetryCallState
import structlog

logger = structlog.get_logger()


def notify_slack_on_final_failure(retry_state: RetryCallState) -> None:
    """Post to Slack #errors channel when all retries are exhausted."""
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    logger.error(
        "api_call_failed_after_retries",
        attempts=retry_state.attempt_number,
        exception=str(exception),
    )
    # Post to Slack #errors channel
    # (Uses SlackNotifier or direct WebClient call)


def resilient_api_call(api_name: str):
    """Decorator factory for resilient API calls."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
        before_sleep=lambda rs: logger.warning(
            "retrying_api_call",
            api=api_name,
            attempt=rs.attempt_number,
        ),
        retry_error_callback=notify_slack_on_final_failure,
        reraise=True,
    )
```

## Discretion Recommendations

### Runtime Model: Long-Running Process
**Recommendation:** Long-running process with asyncio combining FastAPI (HTTP) and Slack Bolt (WebSocket).
**Rationale:** Slack Bolt Socket Mode requires a persistent WebSocket connection. SQLite requires local filesystem. ThreadStateManager uses in-memory state (per prior decision [04-03]). Serverless/event-driven models cannot satisfy these constraints. A single long-running process is the simplest correct approach.
**Confidence:** HIGH -- constraints make this the only viable option.

### Config Management: Hybrid (env vars + config files)
**Recommendation:** Use environment variables for secrets and deployment-specific values (API tokens, webhook secrets, channel IDs, database path). Use config files (YAML) for business logic configuration (escalation triggers, custom field mapping, CPM thresholds). This extends the existing pattern -- the project already uses env vars for `SLACK_BOT_TOKEN`, `ANTHROPIC_API_KEY`, and config YAML for `escalation_triggers.yaml`.
**New env vars needed:**
- `CLICKUP_API_TOKEN` -- ClickUp API access token
- `CLICKUP_WEBHOOK_SECRET` -- HMAC secret from webhook creation
- `CLICKUP_TEAM_ID` -- ClickUp workspace team ID
- `AUDIT_DB_PATH` -- Path to SQLite database file (default: `data/audit.db`)
- `SLACK_ERRORS_CHANNEL` -- Channel ID for error notifications
- `WEBHOOK_PORT` -- Port for FastAPI server (default: 8000)
**New config file:** `config/campaign_fields.yaml` -- maps ClickUp custom field names to campaign model fields
**Confidence:** HIGH -- extends existing patterns in the codebase.

### Logging Format: Structured JSON (production) / Console (development)
**Recommendation:** Use `structlog` with dual-mode configuration: JSON output in production (for log aggregation), human-readable console output in development. Bind contextual data (campaign_id, influencer_name, event_type) to every log message.
**Confidence:** HIGH -- structlog is the standard Python structured logging library and supports this dual-mode pattern natively.

### Retry Backoff Strategy: Exponential with Jitter
**Recommendation:** `wait_exponential_jitter(initial=1, max=30, jitter=5)` -- starts at 1 second, grows exponentially, caps at 30 seconds, adds up to 5 seconds of random jitter. Three attempts total. This prevents thundering herd when multiple negotiations retry simultaneously.
**Confidence:** HIGH -- standard pattern for API retry, tenacity supports it natively.

### SQLite Schema Design
**Recommendation:** Single `audit_log` table with indexes on `influencer_name`, `campaign_id`, and `timestamp`. Use `event_type` (StrEnum) to distinguish entry types. Store `rates_used` and `metadata` as JSON strings for flexibility. This is simpler than multiple tables and sufficient for the query patterns specified (by influencer, by campaign, by date range).

Optional future addition: a `campaigns` table for campaign-level metadata, referenced by `campaign_id` foreign key. For v1, campaign data can be reconstructed from the `campaign_start` audit entries.

**Confidence:** HIGH -- aligns with the query patterns in the requirements and keeps the schema simple.

### Slack Audit Query Response Formatting
**Recommendation:** Use Block Kit with a compact table-like format. Show up to 10 most recent entries per query (Slack has a message size limit of ~50 blocks). Include a summary header (total results, query parameters), then individual entries as `section` blocks with `fields` for key data points. For queries with more results, include a note like "Showing 10 of 47 results. Use CLI for full results."

**Example format:**
```
Audit Trail: Jane Doe (last 7 days)
47 entries found (showing most recent 10)

---
[Feb 19, 2:30 PM] Email Received
Campaign: Spring Collection | State: counter_received
Rate proposed: $2,500 | CPM: $25.00

---
[Feb 19, 2:31 PM] Email Sent
Campaign: Spring Collection | State: counter_sent
Rate offered: $2,200 | CPM: $22.00
```

**Confidence:** MEDIUM -- formatting is subjective and may need iteration based on team feedback.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Polling ClickUp API for task changes | Webhook subscriptions for real-time notifications | ClickUp API v2 (current) | Eliminates polling overhead, real-time data flow |
| SQLite default journal mode | WAL (Write-Ahead Logging) mode | SQLite 3.7.0+ (2010, widely standard) | Concurrent readers + single writer without blocking |
| stdlib `logging` with JSON formatter | `structlog` for structured logging | structlog 21+ (mature, stable) | Contextual binding, processor pipeline, cleaner code |
| Custom retry loops | `tenacity` library | tenacity 8+ (mature, de facto standard) | Handles jitter, async, exception filtering, callbacks |

**Deprecated/outdated:**
- ClickUp API v1: Fully deprecated. All integrations should use v2.
- `aiohttp` for simple webhook receivers: Still works but FastAPI provides more features (validation, docs) with less code.

## Open Questions

1. **ClickUp Custom Field Names**
   - What we know: The campaign form will use custom fields for client name, budget, deliverables, influencer list, CPM range, platform, timeline.
   - What's unclear: The exact custom field names in the ClickUp workspace. These are user-configured and must be mapped in `config/campaign_fields.yaml`.
   - Recommendation: Make the field mapping fully configurable via YAML. Include a setup script or CLI command to list available custom fields from a ClickUp list.

2. **Influencer List Format in ClickUp Form**
   - What we know: One campaign can list multiple influencers. The form needs to capture an influencer list.
   - What's unclear: Whether the influencer list is a comma-separated text field, a multi-select dropdown, or a relationship field in ClickUp.
   - Recommendation: Support both comma-separated text (simplest form field) and list-type custom fields. Parse flexibly.

3. **Engagement Rate Data Source**
   - What we know: The CPM flexibility calculation needs engagement rate data per influencer.
   - What's unclear: Whether engagement rate is in the existing Google Sheet (`InfluencerRow` currently has: name, email, platform, handle, average_views, min_rate, max_rate -- no engagement rate) or comes from the campaign form.
   - Recommendation: Add an optional `engagement_rate` column to the Google Sheet model. If absent, skip engagement-quality weighting and use pure campaign-average CPM logic.

4. **Public Webhook Endpoint Hosting**
   - What we know: ClickUp webhooks require a publicly accessible HTTPS endpoint.
   - What's unclear: How the team plans to expose the webhook endpoint (cloud server, ngrok for development, reverse proxy).
   - Recommendation: Document the requirement clearly. For development use ngrok. For production, deploy behind a reverse proxy with TLS termination. The FastAPI server itself does not need TLS -- the proxy handles that.

## Sources

### Primary (HIGH confidence)
- [ClickUp Webhooks Documentation](https://developer.clickup.com/docs/webhooks) - Event types, payload structure, security, registration
- [ClickUp Task Webhook Payloads](https://developer.clickup.com/docs/webhooktaskpayloads) - Full payload format, custom field structure, history items
- [ClickUp Webhook Signature](https://developer.clickup.com/docs/webhooksignature) - HMAC-SHA256 verification, X-Signature header
- [ClickUp Custom Fields](https://developer.clickup.com/docs/customfields) - Field types, value formats, API structure
- [ClickUp Automation Webhook Payload](https://developer.clickup.com/docs/automationwebhookpayload) - Alternative trigger mechanism
- [Python sqlite3 stdlib documentation](https://docs.python.org/3/library/sqlite3.html) - Connection management, WAL mode, parameterized queries
- [SQLite WAL documentation](https://sqlite.org/wal.html) - Concurrent access, performance characteristics

### Secondary (MEDIUM confidence)
- [Tenacity GitHub](https://github.com/jd/tenacity) and [docs](https://tenacity.readthedocs.io/) - Retry patterns, exponential backoff, jitter, callbacks
- [structlog documentation](https://www.structlog.org/en/stable/logging-best-practices.html) - Best practices, JSON rendering, contextual binding
- [FastAPI webhooks guide](https://fastapi.tiangolo.com/advanced/openapi-webhooks/) - Webhook endpoint patterns
- [Svix: Receive Webhooks with FastAPI](https://www.svix.com/guides/receiving/receive-webhooks-with-python-fastapi/) - Signature verification pattern
- [Going Fast with SQLite and Python](https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/) - WAL mode, autocommit, performance tips
- Existing codebase patterns: `negotiation.slack.triggers` (YAML config + Pydantic validation), `negotiation.sheets.models` (float-to-Decimal coercion), `negotiation.slack.dispatcher` (pre-check gate pattern)

### Tertiary (LOW confidence)
- ClickUp form-to-task mapping: Not fully documented in API docs. Understanding based on ClickUp Help Center articles and community patterns. The exact payload for form-created tasks vs manually created tasks may differ -- needs validation during implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All recommended libraries are well-established with official documentation verified
- Architecture: HIGH - Patterns follow existing codebase conventions (Pydantic models, StrEnum, pure functions for Block Kit, YAML config) and standard Python practices for webhooks/SQLite
- Pitfalls: HIGH - Based on official ClickUp API documentation caveats and well-documented SQLite concurrency issues
- ClickUp form webhook payload specifics: MEDIUM - The exact custom field presence in `taskCreated` webhook payload is not fully documented; the follow-up GET pattern is recommended as a safe default

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days -- all technologies are stable)
