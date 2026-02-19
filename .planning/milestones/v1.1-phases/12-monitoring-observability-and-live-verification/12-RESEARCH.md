# Phase 12: Monitoring, Observability, and Live Verification - Research

**Researched:** 2026-02-19
**Domain:** Observability (Prometheus metrics, Sentry error tracking, request tracing) and live integration testing
**Confidence:** HIGH

## Summary

Phase 12 adds three observability pillars to the existing FastAPI application -- Prometheus metrics, Sentry error reporting bridged through structlog, and request ID tracing -- plus live integration tests and a persistent Gmail watch renewal mechanism. The codebase already has strong foundations: structlog with `merge_contextvars` as the first processor, FastAPI with `/health` and `/ready` endpoints, SQLite state persistence, and pydantic-settings for configuration. All five requirements (OBS-03 through OBS-05, CONFIG-02, CONFIG-03) can be implemented with well-maintained, standard Python libraries.

The Prometheus endpoint is best handled by `prometheus-fastapi-instrumentator` (v7.1.0), which provides automatic HTTP request/latency metrics and a clean API for adding custom Gauges/Counters for business metrics. Sentry integration uses the official `sentry-sdk` (v2.53.0) which auto-detects FastAPI, combined with `structlog-sentry` (v2.2.1) to bridge structlog log events to Sentry as events/breadcrumbs. Request ID middleware should be built directly using structlog's existing `contextvars` module (already configured) with a simple Starlette middleware -- no third-party library needed since the codebase already uses `clear_contextvars`/`bind_contextvars`/`merge_contextvars`. Live tests use pytest's custom marker system (`@pytest.mark.live`) with `conftest.py` hooks for opt-in execution. Gmail watch persistence adds an `expiration` column to the existing SQLite state table and replaces the hardcoded 6-day sleep with an expiration-aware renewal loop.

**Primary recommendation:** Use `prometheus-fastapi-instrumentator` for /metrics, `sentry-sdk` + `structlog-sentry` for error reporting, hand-write a lightweight request-ID middleware leveraging existing structlog contextvars, implement `@pytest.mark.live` with conftest hooks, and persist Gmail watch expiration in the existing SQLite database.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBS-03 | Agent exposes /metrics Prometheus endpoint with HTTP request metrics and custom business metrics (active negotiations, deals closed) | `prometheus-fastapi-instrumentator` v7.1.0 provides automatic HTTP metrics (request counts, latencies, sizes) and custom metric API via `instrumentator.add()`. Custom business Gauges/Counters from `prometheus_client` track active negotiations (query SQLite) and deals closed (Counter incremented on AGREED transition). |
| OBS-04 | Agent reports errors to Sentry with full request context via structlog bridge | `sentry-sdk` v2.53.0 auto-detects FastAPI and captures unhandled exceptions with request context. `structlog-sentry` v2.2.1 `SentryProcessor` bridges structlog error-level logs to Sentry events, carrying all bound structlog fields (including request_id from OBS-05) as Sentry context. |
| OBS-05 | Agent attaches a unique request ID to every inbound request for end-to-end log traceability | Custom Starlette middleware generates UUID4 per request, calls `structlog.contextvars.clear_contextvars()` then `bind_contextvars(request_id=...)`, and sets `X-Request-ID` response header. The existing `merge_contextvars` processor (already first in the chain) ensures every log entry includes the request_id. |
| CONFIG-02 | Agent includes @pytest.mark.live integration tests that verify real Gmail, Sheets, and Slack connections | Custom `@pytest.mark.live` marker registered in conftest.py with `pytest_addoption(--live)` and `pytest_collection_modifyitems` hook to skip by default. Tests use real credentials from environment variables and verify actual API calls (Gmail send/receive, Sheets read, Slack post). |
| CONFIG-03 | Agent persists Gmail watch expiration timestamp and renews relative to actual expiry, not process uptime | Add `gmail_watch_expiration` column to SQLite state schema (or new table). Parse `expiration` field (epoch milliseconds) from `setup_watch()` response, persist it, and replace the hardcoded 6-day `asyncio.sleep` with a loop that calculates sleep duration from `persisted_expiration - now - safety_margin`. On restart, read persisted expiration and renew immediately if expired. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| [prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator) | 7.1.0 | Auto-instrument FastAPI with Prometheus HTTP metrics and expose /metrics endpoint | De facto standard for FastAPI+Prometheus; 1-line setup for default metrics, extensible for custom metrics. ISC license. |
| [prometheus_client](https://github.com/prometheus/client_python) | (transitive dep) | Create custom Gauges and Counters for business metrics | Official Prometheus Python client; pulled in as dependency of instrumentator |
| [sentry-sdk](https://pypi.org/project/sentry-sdk/) | >=2.53.0 | Capture unhandled exceptions and send to Sentry with request context | Official Sentry Python SDK; auto-detects FastAPI integration, captures request metadata automatically |
| [structlog-sentry](https://github.com/kiwicom/structlog-sentry) | 2.2.1 | Bridge structlog log events to Sentry as events/breadcrumbs | Standard structlog-to-Sentry bridge; SentryProcessor integrates directly into structlog processor chain |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| structlog (existing) | >=25.5.0 | Already in codebase; provides contextvars for request_id binding | Request ID middleware uses existing `clear_contextvars`/`bind_contextvars` |
| uuid (stdlib) | N/A | Generate unique request IDs | `uuid.uuid4()` for each inbound HTTP request |
| pytest (existing) | >=9.0 | Test framework with custom markers for live tests | `@pytest.mark.live` with conftest hooks for opt-in execution |
| sqlite3 (stdlib) | N/A | Already used for state persistence; extend for watch expiration | Add column or table for Gmail watch expiration timestamp |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| prometheus-fastapi-instrumentator | starlette-exporter | instrumentator is more feature-rich with custom metric API and gzip support; starlette-exporter is simpler but less flexible |
| structlog-sentry | Manual sentry_sdk.capture_exception calls | structlog-sentry automates the bridge; manual calls miss logs that aren't exceptions |
| Custom request_id middleware | asgi-correlation-id | asgi-correlation-id is a full library but adds a dependency for something achievable in ~20 lines using existing structlog contextvars. The codebase already has the contextvars infrastructure. |
| Custom request_id middleware | fastapi-structlog | fastapi-structlog bundles logging, middleware, and Sentry -- but it replaces the existing structlog setup, which is already well-configured. Too invasive. |

**Installation:**
```bash
pip install prometheus-fastapi-instrumentator sentry-sdk structlog-sentry
```

Or add to `pyproject.toml` dependencies:
```toml
"prometheus-fastapi-instrumentator>=7.1.0",
"sentry-sdk>=2.53.0",
"structlog-sentry>=2.2.1",
```

## Architecture Patterns

### Recommended Project Structure
```
src/negotiation/
├── app.py                  # Add instrumentator setup and Sentry init
├── config.py               # Add sentry_dsn, enable_metrics settings
├── health.py               # Existing /health and /ready (unchanged)
├── observability/
│   ├── __init__.py
│   ├── metrics.py          # Prometheus instrumentator + custom business metrics
│   ├── sentry.py           # Sentry SDK init + structlog-sentry processor setup
│   └── middleware.py        # Request ID middleware
├── state/
│   ├── schema.py           # Add gmail_watch_state table DDL
│   └── watch_store.py      # Gmail watch expiration persistence
tests/
├── conftest.py             # Add @pytest.mark.live registration + hooks
├── live/                   # Live integration tests directory
│   ├── conftest.py         # Live-specific fixtures (real credentials)
│   ├── test_gmail_live.py  # Gmail send/receive verification
│   ├── test_sheets_live.py # Sheets read verification
│   └── test_slack_live.py  # Slack message delivery verification
├── test_metrics.py         # Unit tests for /metrics endpoint
├── test_sentry.py          # Unit tests for Sentry integration
└── test_request_id.py      # Unit tests for request ID middleware
```

### Pattern 1: Prometheus Instrumentator with Custom Business Metrics
**What:** Use `prometheus-fastapi-instrumentator` for HTTP metrics plus custom `prometheus_client` Gauges/Counters for business KPIs.
**When to use:** When you need both standard HTTP observability and domain-specific metrics on the same /metrics endpoint.
**Example:**
```python
# Source: https://github.com/trallnag/prometheus-fastapi-instrumentator
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# Custom business metrics
ACTIVE_NEGOTIATIONS = Gauge(
    "negotiation_active_total",
    "Number of currently active (non-terminal) negotiations",
)
DEALS_CLOSED = Counter(
    "negotiation_deals_closed_total",
    "Total number of deals closed (AGREED state)",
)

def setup_metrics(app: FastAPI) -> None:
    """Instrument FastAPI app with Prometheus metrics."""
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/ready", "/metrics"],
    ).instrument(app).expose(app, include_in_schema=False)
```

### Pattern 2: Sentry + structlog Bridge
**What:** Initialize Sentry SDK with FastAPI auto-detection, then insert `SentryProcessor` into the structlog processor chain.
**When to use:** When you want unhandled exceptions AND structlog error-level logs to both report to Sentry with full context.
**Example:**
```python
# Source: https://github.com/kiwicom/structlog-sentry + https://docs.sentry.io/platforms/python/integrations/fastapi/
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from structlog_sentry import SentryProcessor

def init_sentry(dsn: str) -> None:
    """Initialize Sentry SDK with FastAPI auto-detection."""
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.1,
        # Disable default logging integration -- structlog-sentry handles it
        integrations=[LoggingIntegration(event_level=None, level=None)],
        send_default_pii=False,
    )

# In configure_logging(), add SentryProcessor to structlog chain:
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    SentryProcessor(event_level=logging.ERROR),  # <-- NEW: before renderer
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]
```

### Pattern 3: Request ID Middleware via structlog contextvars
**What:** Starlette middleware that generates UUID4 per request, binds it to structlog contextvars, and returns it in response headers.
**When to use:** When you need end-to-end log traceability across all log messages within a single request.
**Example:**
```python
# Source: https://www.structlog.org/en/latest/contextvars.html
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### Pattern 4: Gmail Watch Expiration Persistence
**What:** Store `expiration` from Gmail watch API response in SQLite and compute renewal sleep from actual expiry.
**When to use:** When process restarts must not cause missed emails because the renewal timer reset.
**Example:**
```python
# Persist expiration after setup_watch
watch_result = gmail_client.setup_watch(topic)
expiration_ms = int(watch_result.get("expiration", 0))
watch_store.save_expiration(expiration_ms)

# Renewal loop uses persisted expiration
async def renew_gmail_watch(services, watch_store):
    SAFETY_MARGIN = 3600  # 1 hour before actual expiry
    while True:
        expiration_ms = watch_store.load_expiration()
        now_ms = int(time.time() * 1000)
        sleep_seconds = max(0, (expiration_ms - now_ms) / 1000 - SAFETY_MARGIN)
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)
        # Renew and persist new expiration
        result = gmail_client.setup_watch(topic)
        watch_store.save_expiration(int(result.get("expiration", 0)))
```

### Pattern 5: Opt-in Live Test Markers
**What:** Register `@pytest.mark.live` with conftest hooks; tests are skipped unless `pytest --live` is passed.
**When to use:** When integration tests require real credentials and should not run in normal CI.
**Example:**
```python
# conftest.py
def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="run live integration tests")

def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as live integration test (requires real credentials)")

def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return  # Run all tests including live
    skip_live = pytest.mark.skip(reason="need --live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
```

### Anti-Patterns to Avoid
- **Instrumenting every route including health/metrics:** Exclude `/health`, `/ready`, and `/metrics` from Prometheus instrumentation to avoid self-referential metric noise.
- **Sending PII to Sentry:** Set `send_default_pii=False` and avoid binding email addresses or personal data to structlog context that flows to Sentry. Use influencer IDs instead.
- **Relying on process uptime for Gmail watch renewal:** The current `renew_gmail_watch_periodically` sleeps for 6 days based on process start time. If the process restarts at day 5, it sleeps another 6 days, missing the 7-day expiry. Always persist and compute from the actual expiration timestamp.
- **Blocking the event loop with synchronous Prometheus queries:** The `ACTIVE_NEGOTIATIONS` gauge should be updated at state transitions, not by querying SQLite on every /metrics scrape.
- **Placing SentryProcessor after the renderer:** SentryProcessor must come before the renderer (JSONRenderer/ConsoleRenderer) in the structlog chain to receive structured event dicts, not formatted strings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP request metrics (count, latency, size) | Custom Starlette middleware with prometheus_client | `prometheus-fastapi-instrumentator` | Handles route grouping, status code grouping, in-progress tracking, histogram buckets, gzip compression -- 50+ edge cases |
| Sentry event capture from structlog | Manual `sentry_sdk.capture_exception()` calls in try/except | `structlog-sentry` SentryProcessor | Automatically captures all error-level logs as Sentry events with context, not just caught exceptions |
| Prometheus exposition format | Custom /metrics endpoint that formats metrics manually | `prometheus_client.generate_latest()` via instrumentator.expose() | Prometheus text format has strict conventions (multiline, type annotations, HELP lines) |
| Sentry FastAPI integration | Manual ASGI middleware for error capture | `sentry-sdk` auto-detect | The SDK already intercepts exceptions, attaches request context, manages scopes -- reimplementing is error-prone |

**Key insight:** Observability libraries handle numerous edge cases (metric cardinality explosion, Sentry rate limiting, thread-safe context propagation) that are not obvious until production. The libraries listed here are the standard tools used by the Python/FastAPI ecosystem.

## Common Pitfalls

### Pitfall 1: Metric Cardinality Explosion
**What goes wrong:** Uncontrolled label values (e.g., user IDs, full URLs with query params) create thousands of time series, overwhelming Prometheus.
**Why it happens:** Custom metrics with unbounded label values. Route handlers with path parameters become distinct series per parameter value.
**How to avoid:** Use `should_group_status_codes=True`, `should_ignore_untemplated=True`. For custom metrics, use bounded label sets (state names, not IDs). Never use user-specific values as labels.
**Warning signs:** Prometheus scrape time increasing, memory usage growing, "too many time series" alerts.

### Pitfall 2: structlog contextvars Sync/Async Boundary
**What goes wrong:** Context variables set in async middleware don't propagate to synchronous helper threads (e.g., `asyncio.to_thread` calls to GmailClient).
**Why it happens:** Python's `contextvars` automatically copy context to new threads in `asyncio.to_thread`, but some execution models don't preserve this.
**How to avoid:** `asyncio.to_thread` does copy context (verified in Python 3.12). The codebase already uses `asyncio.to_thread` for Gmail calls, so `request_id` will propagate. Test this behavior explicitly.
**Warning signs:** Log entries from GmailClient calls missing `request_id` field.

### Pitfall 3: SentryProcessor Placement in structlog Chain
**What goes wrong:** Sentry receives formatted strings instead of structured event dicts, losing all context fields.
**Why it happens:** SentryProcessor is placed after the renderer (JSONRenderer/ConsoleRenderer).
**How to avoid:** Insert SentryProcessor BEFORE the renderer but AFTER `add_log_level` (SentryProcessor needs the log level). Also place it before `format_exc_info` if used.
**Warning signs:** Sentry events show raw JSON/text strings instead of structured fields.

### Pitfall 4: Double Sentry Reporting
**What goes wrong:** Both `sentry-sdk`'s built-in logging integration AND `structlog-sentry` report the same error, creating duplicate events.
**Why it happens:** `sentry-sdk` auto-enables `LoggingIntegration` which captures stdlib logging events. If structlog is configured to also log through stdlib, events are captured twice.
**How to avoid:** Disable Sentry's `LoggingIntegration` when using `structlog-sentry`: `LoggingIntegration(event_level=None, level=None)`.
**Warning signs:** Duplicate Sentry events for the same error.

### Pitfall 5: Live Tests Running in CI Accidentally
**What goes wrong:** Live tests that call real APIs run in CI, either failing (no credentials) or creating real side effects (sending emails).
**Why it happens:** Tests not properly gated behind `--live` flag, or CI config accidentally includes the flag.
**How to avoid:** Use `pytest_collection_modifyitems` to skip by default. Add clear `reason="need --live option"` messages. Never include `--live` in the default pytest configuration.
**Warning signs:** CI failures with "authentication" or "credential" errors in test logs.

### Pitfall 6: Gmail Watch Expiration Off-by-One After Restart
**What goes wrong:** On restart, the app calls `setup_watch()` but doesn't persist the new expiration, so the renewal loop uses stale data.
**Why it happens:** The renewal code path only persists on periodic renewal, not on startup.
**How to avoid:** Always persist expiration after every `setup_watch()` call, both at startup and in the renewal loop.
**Warning signs:** After restart, the app renews watch too early or too late based on stale stored expiration.

## Code Examples

Verified patterns from official sources:

### Prometheus Instrumentator Setup (OBS-03)
```python
# Source: https://github.com/trallnag/prometheus-fastapi-instrumentator
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# Module-level business metrics
ACTIVE_NEGOTIATIONS = Gauge(
    "negotiation_active_total",
    "Number of currently active (non-terminal) negotiations",
)
DEALS_CLOSED = Counter(
    "negotiation_deals_closed_total",
    "Total number of negotiations reaching AGREED state",
)

def setup_metrics(app: FastAPI) -> None:
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/ready", "/metrics"],
    ).instrument(app).expose(
        app,
        include_in_schema=False,
        should_gzip=True,
    )
```

### Sentry Initialization with structlog Bridge (OBS-04)
```python
# Sources: https://docs.sentry.io/platforms/python/integrations/fastapi/
#          https://github.com/kiwicom/structlog-sentry
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from structlog_sentry import SentryProcessor

def init_sentry(dsn: str) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
        integrations=[
            LoggingIntegration(event_level=None, level=None),
        ],
    )

# Add to configure_logging() processor chain:
# SentryProcessor goes AFTER add_log_level, BEFORE TimeStamper/renderer
shared_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    SentryProcessor(event_level=logging.ERROR),
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]
```

### Request ID Middleware (OBS-05)
```python
# Source: https://www.structlog.org/en/latest/contextvars.html
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Accept client-provided ID or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Clear previous request's context and bind new ID
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            # Re-bind service name that was set at startup
            service="negotiation-agent",
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### Live Test Conftest Hooks (CONFIG-02)
```python
# Source: https://til.simonwillison.net/pytest/only-run-integration
# conftest.py (root level)
import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--live", action="store_true", default=False,
        help="run live integration tests that require real service credentials",
    )

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: mark test as live integration test (requires real credentials, skipped by default)",
    )

def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="need --live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
```

### Gmail Watch Expiration Persistence (CONFIG-03)
```python
# Schema for watch state
CREATE TABLE IF NOT EXISTS gmail_watch_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    expiration_ms INTEGER NOT NULL,
    history_id TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

# WatchStore class
class GmailWatchStore:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, expiration_ms: int, history_id: str) -> None:
        now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._conn.execute(
            "INSERT OR REPLACE INTO gmail_watch_state (id, expiration_ms, history_id, updated_at) VALUES (1, ?, ?, ?)",
            (expiration_ms, history_id, now),
        )
        self._conn.commit()

    def load(self) -> tuple[int, str] | None:
        cursor = self._conn.execute("SELECT expiration_ms, history_id FROM gmail_watch_state WHERE id = 1")
        row = cursor.fetchone()
        return (row[0], row[1]) if row else None
```

### Config Settings Additions
```python
# New fields in Settings class (config.py)
class Settings(BaseSettings):
    # ... existing fields ...

    # -- Observability (Phase 12) -------------------------------------------
    sentry_dsn: str = ""                    # Empty = Sentry disabled
    enable_metrics: bool = True             # Toggle Prometheus metrics
    gmail_watch_safety_margin_seconds: int = 3600  # Renew 1h before expiry
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom /metrics endpoint | prometheus-fastapi-instrumentator | Stable since v6+ (2023) | No need to hand-write metric exposition |
| Manual sentry_sdk.capture_exception() | structlog-sentry SentryProcessor | Available since 2020, stable API | Automatic bridge for all structlog error logs |
| asgi-correlation-id for request IDs | structlog.contextvars (built-in) | structlog 21.1+ | No extra dependency needed when structlog is already configured |
| Timer-based Gmail watch renewal | Expiration-aware renewal from persisted timestamp | Gmail API always returned expiration; persistence was overlooked | Survives process restarts without missed emails |

**Deprecated/outdated:**
- `@app.on_event("startup")` for instrumentator setup -- use lifespan context manager instead (already done in codebase)
- `sentry-sdk` v1.x API -- v2.x changed initialization patterns; always use `sentry_sdk.init()` (same in v2.53.0)

## Open Questions

1. **Sentry DSN provisioning**
   - What we know: Sentry requires a DSN (Data Source Name) to send events. The `sentry_dsn` setting will be empty by default (disabled).
   - What's unclear: Whether the team already has a Sentry organization/project or needs to create one.
   - Recommendation: Add `sentry_dsn` to Settings with empty default. Sentry init is a no-op when DSN is empty. The team can provision a Sentry project independently.

2. **Live test credential management**
   - What we know: Tests need real Gmail OAuth token, Sheets service account key, and Slack bot token.
   - What's unclear: How credentials will be provided in the live test environment (local `.env` file vs. CI secrets).
   - Recommendation: Live test fixtures should read from environment variables (same names as production config). Document required env vars. Do NOT commit credentials.

3. **Business metric update strategy for active negotiations**
   - What we know: `ACTIVE_NEGOTIATIONS` Gauge needs to reflect the count of non-terminal negotiations.
   - What's unclear: Whether to query SQLite on each state change or maintain an in-memory counter.
   - Recommendation: Increment/decrement the Gauge at state transitions (when a negotiation starts and when it reaches a terminal state). This is event-driven and avoids polling SQLite. The in-memory `negotiation_states` dict size can serve as a cross-check.

## Sources

### Primary (HIGH confidence)
- [prometheus-fastapi-instrumentator GitHub](https://github.com/trallnag/prometheus-fastapi-instrumentator) - Installation, usage, custom metrics API, v7.1.0 documentation
- [Sentry FastAPI Integration Docs](https://docs.sentry.io/platforms/python/integrations/fastapi/) - SDK initialization, auto-detection, request context capture, configuration options
- [structlog-sentry GitHub](https://github.com/kiwicom/structlog-sentry) - SentryProcessor setup, configuration options, structlog chain placement
- [structlog Context Variables Docs](https://www.structlog.org/en/latest/contextvars.html) - bind_contextvars, clear_contextvars, merge_contextvars usage and caveats
- [Gmail API users.watch Reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/watch) - Response format (expiration in epoch ms, historyId)
- [Gmail Push Notifications Guide](https://developers.google.com/workspace/gmail/api/guides/push) - Watch renewal requirements, 7-day expiry

### Secondary (MEDIUM confidence)
- [Simon Willison's TIL: Opt-in integration tests](https://til.simonwillison.net/pytest/only-run-integration) - Verified pattern for pytest custom markers with conftest hooks
- [sentry-sdk PyPI](https://pypi.org/project/sentry-sdk/) - Version 2.53.0 (released 2026-02-16), Python >=3.6
- [prometheus-fastapi-instrumentator PyPI](https://pypi.org/project/prometheus-fastapi-instrumentator/) - Version 7.1.0 (released 2025-03-19), Python >=3.8
- [structlog-sentry PyPI](https://pypi.org/project/structlog-sentry/) - Version 2.2.1, limited recent activity but stable API

### Tertiary (LOW confidence)
- None -- all critical findings verified with official sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified on PyPI/GitHub with current versions and active maintenance (except structlog-sentry which is stable but low-activity)
- Architecture: HIGH - Patterns verified against official documentation and existing codebase structure
- Pitfalls: HIGH - Drawn from official docs (structlog contextvars caveats, Sentry double-reporting, Gmail watch expiry semantics)

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days -- stable domain, libraries not fast-moving)
