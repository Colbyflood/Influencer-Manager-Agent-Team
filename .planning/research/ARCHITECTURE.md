# Architecture Research

**Domain:** Production readiness for AI-powered influencer negotiation agent (FastAPI + services dict + SQLite)
**Researched:** 2026-02-19
**Confidence:** HIGH for patterns; MEDIUM for specific library versions (verified against current docs where possible)

---

## Scope and Context

This document focuses exclusively on how production readiness features integrate with the **existing** architecture. The existing system is not being redesigned — it is being hardened. Every recommendation below specifies whether it is a **new component** or a **modification to an existing component**, and which existing file/pattern it touches.

### Existing Architecture Snapshot

```
src/negotiation/
├── app.py                    # FastAPI entry point; initialize_services(), create_app(), main()
│   ├── services dict         # Central dependency container — ALL shared objects live here
│   ├── negotiation_states    # services["negotiation_states"]: dict[thread_id -> state]
│   ├── history_lock          # services["history_lock"]: asyncio.Lock (Gmail race protection)
│   └── background_tasks      # services["background_tasks"]: set[asyncio.Task]
├── audit/
│   ├── store.py              # SQLite init_audit_db(), insert_audit_entry(), query_audit_trail()
│   └── logger.py             # AuditLogger wrapping store.py
├── state_machine/
│   └── machine.py            # NegotiationStateMachine: pure Python, _state + _history fields
├── slack/
│   └── takeover.py           # ThreadStateManager: in-memory dict[thread_id -> {managed_by, claimed_by}]
├── campaign/
│   └── webhook.py            # GET /health (exists), POST /webhooks/clickup
└── resilience/
    └── retry.py              # tenacity wrapper, configure_error_notifier()
```

### What "Production Readiness" Means Here

| Concern | Current State | Target State |
|---------|--------------|--------------|
| Negotiation state | In-memory dict (lost on restart) | Redis-backed, survives container restart |
| Thread state (human takeover) | In-memory dict (lost on restart) | Redis-backed |
| Gmail history_id | In-memory string (lost on restart) | Redis-backed |
| Audit store | SQLite file on local disk | SQLite on Docker named volume (keep SQLite) |
| Deployment | Run directly with Python | Dockerized, docker-compose managed |
| Health checks | `/health` returns `{"status": "healthy"}` unconditionally | Liveness + readiness probes with dependency checks |
| CI/CD | None | GitHub Actions: test -> build -> push -> deploy |
| Monitoring | structlog JSON to stdout | Prometheus metrics at `/metrics` + log aggregation ready |
| Error handling | tenacity + Slack error notifier (exists) | Structured error boundary + dead-letter logging |

---

## Recommended Architecture: Production Integration

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                             │
│  Gmail Pub/Sub   Slack Socket Mode   ClickUp Webhooks   Anthropic    │
└─────────┬────────────────┬───────────────────┬──────────────────────-┘
          │                │                   │
┌─────────▼────────────────▼───────────────────▼───────────────────────┐
│                        DOCKER HOST (VM)                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  negotiation-agent container                                   │  │
│  │                                                                │  │
│  │  FastAPI (uvicorn, port 8000)                                  │  │
│  │  ├── POST /webhooks/gmail          ─── process_inbound_email() │  │
│  │  ├── POST /webhooks/clickup        ─── campaign_processor()    │  │
│  │  ├── GET /health/liveness          [NEW] always 200 if alive   │  │
│  │  ├── GET /health/readiness         [NEW] checks Redis + SQLite │  │
│  │  └── GET /metrics                  [NEW] Prometheus scrape     │  │
│  │                                                                │  │
│  │  services dict (app.state.services)                            │  │
│  │  ├── redis_client [NEW]            async redis.Redis           │  │
│  │  ├── audit_conn                    sqlite3.Connection (keep)   │  │
│  │  ├── audit_logger                  AuditLogger (keep)          │  │
│  │  ├── gmail_client                  GmailClient (keep)          │  │
│  │  ├── slack_dispatcher              SlackDispatcher (keep)      │  │
│  │  ├── anthropic_client              Anthropic (keep)            │  │
│  │  ├── thread_state_manager [MOD]    RedisThreadStateManager     │  │
│  │  └── negotiation_states [MOD]      RedisNegotiationStateStore  │  │
│  │                                                                │  │
│  │  Slack Bolt Socket Mode (thread, via asyncio.to_thread)        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────┐    ┌────────────────────────────────────────┐ │
│  │  redis container  │    │  Named Docker Volume: negotiation-data │ │
│  │  port 6379        │    │  /data/audit.db  (SQLite WAL mode)     │ │
│  │  AOF persistence  │    │  /data/tokens/   (OAuth credentials)   │ │
│  └───────────────────┘    └────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Component Integration Map

### New Components (must be built)

| Component | File Location | Purpose | Integrates With |
|-----------|--------------|---------|-----------------|
| `RedisNegotiationStateStore` | `src/negotiation/state/redis_store.py` | Replaces `services["negotiation_states"]` dict | `process_inbound_email()` in `app.py` |
| `RedisThreadStateManager` | `src/negotiation/slack/redis_takeover.py` | Replaces `ThreadStateManager` in-memory store | `SlackDispatcher`, `/claim`, `/resume` commands |
| Health endpoints module | `src/negotiation/health/endpoints.py` | Liveness + readiness with real dependency checks | `create_app()` in `app.py` |
| Prometheus instrumentation | Inside `create_app()` in `app.py` | `prometheus-fastapi-instrumentator` | FastAPI app instance |
| `Dockerfile` | repo root | Multi-stage build for production image | GitHub Actions CI/CD |
| `docker-compose.yml` | repo root | Orchestrate app + redis containers | Local dev and VM deployment |
| `.github/workflows/ci.yml` | `.github/workflows/` | Test -> build -> push -> SSH deploy | GitHub, GHCR or Docker Hub, VM |

### Modified Components (existing files change)

| Component | File | What Changes | Why |
|-----------|------|-------------|-----|
| `initialize_services()` | `app.py` | Add Redis client init, swap `ThreadStateManager` for `RedisThreadStateManager`, swap `negotiation_states` dict for `RedisNegotiationStateStore` | Persistence |
| `lifespan()` | `app.py` | Add Redis connection close on shutdown, add Redis-based history_id persistence | Persistence |
| `create_app()` | `app.py` | Register health router, add Prometheus instrumentation | Observability |
| `/health` endpoint | `campaign/webhook.py` | Existing endpoint stays, but add richer health router alongside it | Backward compat |
| `configure_logging()` | `app.py` | No code change needed — JSON already configured for `PRODUCTION=true`; add `request_id` binding via middleware | Traceability |

---

## Data Flow Changes

### negotiation_states: In-Memory Dict -> Redis

**Current flow** (`app.py`, `start_negotiations_for_campaign`, `process_inbound_email`):

```python
# Write (start_negotiations_for_campaign)
negotiation_states[thread_id] = {
    "state_machine": state_machine,    # NegotiationStateMachine object
    "context": context,                # plain dict
    "round_count": 0,
    "campaign": campaign,              # Campaign pydantic model
    "cpm_tracker": cpm_tracker,        # CampaignCPMTracker object
}

# Read (process_inbound_email)
thread_state = negotiation_states.get(inbound.thread_id)
state_machine = thread_state["state_machine"]
context = thread_state["context"]
```

**New flow** (Redis-backed store, same interface surface):

```python
# Write
await state_store.set(thread_id, {
    "state": state_machine.state,          # StrEnum -> str, serializable
    "history": state_machine.history,      # list[tuple] -> JSON array of arrays
    "context": context,                    # plain dict -> JSON directly
    "round_count": 0,
    "campaign_id": campaign.campaign_id,   # string ref, not full object
    "cpm_tracker_state": {...},            # CampaignCPMTracker fields, not object
})

# Read
raw = await state_store.get(inbound.thread_id)
if raw:
    sm = NegotiationStateMachine(initial_state=NegotiationState(raw["state"]))
    sm._history = [tuple(h) for h in raw["history"]]
    # reconstruct context, round_count from raw dict directly
```

**Key serialization decision:** Store `state_machine.state` (StrEnum value string) and `state_machine.history` (list of tuples), NOT the `NegotiationStateMachine` object. Reconstruct the machine from these primitives on read. This avoids pickle, which is unsafe for Redis. Confidence: HIGH — the `NegotiationStateMachine` class is pure Python with no external dependencies; all its data fits cleanly in JSON.

**CampaignCPMTracker**: Store its scalar fields (campaign_id, target_min_cpm, target_max_cpm, total_influencers, deals_closed, total_spend) rather than the object. Reconstruct on read. Inspect `src/negotiation/campaign/cpm_tracker.py` during implementation to confirm field list.

### ThreadStateManager: In-Memory Dict -> Redis

**Current flow** (`slack/takeover.py`):

```python
self._state: dict[str, dict[str, str | None]] = {}

def claim_thread(self, thread_id, user_id):
    self._state[thread_id] = {"managed_by": "human", "claimed_by": user_id}

def is_human_managed(self, thread_id) -> bool:
    entry = self._state.get(thread_id)
    return entry is not None and entry["managed_by"] == "human"
```

**New flow** (`slack/redis_takeover.py`):

```python
class RedisThreadStateManager:
    """Drop-in Redis-backed replacement for ThreadStateManager.

    Interface is identical to ThreadStateManager — all existing callers
    in SlackDispatcher and slash command handlers work unchanged.
    """

    def __init__(self, redis_client: redis.asyncio.Redis) -> None:
        self._redis = redis_client
        self._key_prefix = "thread_state:"

    async def claim_thread(self, thread_id: str, user_id: str) -> None:
        key = f"{self._key_prefix}{thread_id}"
        await self._redis.hset(key, mapping={"managed_by": "human", "claimed_by": user_id})

    async def is_human_managed(self, thread_id: str) -> bool:
        val = await self._redis.hget(f"{self._key_prefix}{thread_id}", "managed_by")
        return val == b"human"
```

**Callsite impact**: `SlackDispatcher.pre_check()` and slash command handlers call `thread_state_manager.claim_thread()` and `is_human_managed()`. These become async calls. Callers need `await`. Audit all callers when implementing. The `pre_check()` method in `src/negotiation/slack/dispatcher.py` must be verified — if it is currently synchronous, it needs to become async.

### Gmail history_id: In-Memory String -> Redis

**Current flow** (`app.py`, `lifespan`, `/webhooks/gmail`):

```python
services["history_id"] = ""       # set at startup after watch registration
services["history_lock"] = asyncio.Lock()

# On notification:
async with svc["history_lock"]:
    current_history_id = svc.get("history_id", "")
    new_ids, new_history_id = await asyncio.to_thread(...)
    svc["history_id"] = new_history_id
```

**New flow** (Redis string, lock becomes Redis-side atomic op):

```python
# In lifespan startup:
history_id = await redis_client.get("gmail:history_id")
if history_id:
    services["history_id"] = history_id.decode()  # restore after restart
else:
    services["history_id"] = ""  # first start

# On notification (atomic compare-and-set via Redis):
async with svc["history_lock"]:  # Keep asyncio.Lock for in-process safety
    new_ids, new_history_id = await asyncio.to_thread(...)
    svc["history_id"] = new_history_id
    await redis_client.set("gmail:history_id", new_history_id)
```

The `asyncio.Lock` stays for in-process concurrency protection. The Redis write persists the value so it survives restarts.

---

## New Components: Detailed Specs

### 1. Health Endpoints (`src/negotiation/health/endpoints.py`)

**Pattern:** Two separate endpoints following Kubernetes liveness/readiness conventions. Even on a VM with Docker, Docker's own `HEALTHCHECK` uses the same endpoints.

```python
# LIVENESS — is the process alive and not deadlocked?
# Returns 200 immediately. No dependency checks. If this fails, restart the container.
GET /health/liveness -> {"status": "alive"}

# READINESS — can the service handle requests?
# Returns 200 only if all required dependencies respond. If this fails, stop routing traffic.
GET /health/readiness -> {
    "status": "ready" | "degraded",
    "checks": {
        "redis": "ok" | "error",
        "sqlite": "ok" | "error",
        "gmail_watch": "ok" | "not_configured"
    }
}
```

**Readiness check implementation:**

```python
async def check_redis(redis_client) -> str:
    try:
        await redis_client.ping()
        return "ok"
    except Exception:
        return "error"

def check_sqlite(audit_conn) -> str:
    try:
        audit_conn.execute("SELECT 1")
        return "ok"
    except Exception:
        return "error"
```

**Integration with `create_app()`**: Add `app.include_router(health_router)` inside `create_app()`. The health router needs access to `services` — pass via `app.state.services` same as existing webhook pattern.

**Existing `/health` endpoint** in `campaign/webhook.py` stays untouched. The new endpoints are at `/health/liveness` and `/health/readiness` (different paths, no conflict).

**Docker HEALTHCHECK** (in Dockerfile):

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/liveness')" || exit 1
```

Use liveness (not readiness) for Docker HEALTHCHECK to avoid restarting a healthy container that happens to have a transient Redis blip.

### 2. Redis Client Init in `initialize_services()`

**Where:** `app.py`, `initialize_services()` function, before other services that depend on it.

```python
import redis.asyncio as aioredis

# Add to initialize_services() as step "a.0" (before audit db):
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = aioredis.from_url(redis_url, decode_responses=False)
services["redis_client"] = redis_client
```

**Why `decode_responses=False`**: History IDs and thread state values are bytes from Redis. JSON serialization produces str which we encode to bytes for storage, decode on retrieval. Using `decode_responses=False` keeps the choice explicit at the call site.

**Shutdown** — add to `lifespan()` after yield:

```python
redis_client = services.get("redis_client")
if redis_client:
    await redis_client.aclose()
```

**Dependency**: `redis[asyncio]` — add to `pyproject.toml` dependencies.

### 3. Prometheus Metrics (`create_app()`)

**Library**: `prometheus-fastapi-instrumentator` — MEDIUM confidence, verify version at PyPI.

```python
from prometheus_fastapi_instrumentator import Instrumentator

def create_app(services: dict[str, Any]) -> FastAPI:
    fastapi_app = FastAPI(...)
    fastapi_app.state.services = services
    fastapi_app.include_router(webhook_router)
    fastapi_app.include_router(health_router)  # NEW

    # Prometheus metrics — instrument and expose /metrics
    Instrumentator().instrument(fastapi_app).expose(fastapi_app)  # NEW

    return fastapi_app
```

This adds `GET /metrics` with default RED metrics (request rate, error rate, duration). Prometheus can scrape this endpoint from the Docker host or from a separate Prometheus container.

**Custom metrics to add** (optional, implement in Phase 2+ of production readiness):
- `negotiation_states_active` (Gauge): `len(negotiation_states)` on each request
- `emails_processed_total` (Counter): increment in `process_inbound_email()`
- `llm_call_duration_seconds` (Histogram): wrap Anthropic calls

### 4. Request ID Middleware

**Where:** `create_app()` in `app.py`.

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response
```

This propagates a request ID through all structlog log entries for a given request. structlog already uses `merge_contextvars` in its processor chain (`configure_logging()` line 64), so this integrates without changing the logging config.

---

## Dockerfile

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

# Copy dependency files (cache layer — invalidates only when deps change)
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev group)
RUN uv sync --frozen --no-dev

# Copy source code (invalidates cache on every code change)
COPY src/ ./src/
COPY config/ ./config/
COPY knowledge_base/ ./knowledge_base/

# Create data directory for SQLite (overridden by volume in production)
RUN mkdir -p /app/data

# Non-root user for security
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

# Health check uses liveness endpoint (no external deps required)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/liveness')" || exit 1

EXPOSE 8000

CMD ["python", "-m", "negotiation.app"]
```

**Why python:3.12-slim not python:3.12-alpine:** Alpine has musl libc which breaks some Python C extensions (particularly ones in google-api-python-client). Slim is smaller than the full image but avoids Alpine compatibility issues. Confidence: MEDIUM.

---

## docker-compose.yml

```yaml
services:
  app:
    build: .
    image: negotiation-agent:latest
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - PRODUCTION=true
      - REDIS_URL=redis://redis:6379/0
      - AUDIT_DB_PATH=/data/audit.db
      # Secrets injected via .env file or Docker secrets
    env_file:
      - .env
    volumes:
      - negotiation-data:/data
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/liveness')"]
      interval: 30s
      timeout: 5s
      start_period: 30s
      retries: 3

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --appendfsync everysec
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  negotiation-data:    # SQLite audit.db + OAuth token files
  redis-data:          # Redis AOF persistence
```

**SQLite on Docker volume**: The existing `AUDIT_DB_PATH` env var already controls SQLite path. Set it to `/data/audit.db` which maps to the named volume. The WAL mode already configured in `init_audit_db()` is compatible with single-container volume mounts. Confidence: HIGH — SQLite WAL on a single host with Docker named volumes is a confirmed working pattern per SQLite documentation.

**Redis persistence**: `--appendonly yes --appendfsync everysec` enables AOF mode. This writes every second, balancing durability against performance. A crash can lose at most 1 second of state changes. For negotiation state (threads spanning hours), this is acceptable. Confidence: HIGH — documented Redis persistence option.

---

## GitHub Actions CI/CD

### Workflow: `.github/workflows/ci.yml`

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: uv sync --frozen
      - name: Lint
        run: uv run ruff check src/ tests/
      - name: Type check
        run: uv run mypy src/
      - name: Test
        run: uv run pytest tests/ --tb=short -q
        env:
          AUDIT_DB_PATH: /tmp/test-audit.db

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:latest,ghcr.io/${{ github.repository }}:${{ github.sha }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to VM via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VM_HOST }}
          username: ${{ secrets.VM_USER }}
          key: ${{ secrets.VM_SSH_KEY }}
          script: |
            cd /opt/negotiation-agent
            docker compose pull app
            docker compose up -d --no-deps app
            docker compose ps
```

**Required GitHub Secrets**: `VM_HOST`, `VM_USER`, `VM_SSH_KEY`, plus all application secrets in `.env` on the VM (not in GitHub Secrets for app secrets — manage on server directly or use Docker secrets).

**GHCR vs Docker Hub**: Use GHCR (`ghcr.io`) — it uses `GITHUB_TOKEN` (no extra secret needed), private repos are free for GitHub users, and images are colocated with the repository. Confidence: HIGH.

**Deployment strategy**: `docker compose pull app && docker compose up -d --no-deps app` pulls the new image and restarts only the app container, leaving Redis untouched. This is zero-configuration blue-green on a single VM. Confidence: HIGH.

---

## Error Handling Integration

### Existing: tenacity + Slack notifier

The `resilience/retry.py` module already wraps external API calls with 3-attempt exponential backoff and Slack error notification on exhaustion. This is well-integrated and requires no changes.

### New: Unhandled exception middleware

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    structlog.get_logger().exception(
        "Unhandled exception in request handler",
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

**Where it goes:** `create_app()` in `app.py`. This ensures exceptions in webhook handlers (not just background tasks) produce structured log entries rather than uvicorn's default traceback format.

### Background task error logging

The existing pattern in `app.py` wraps background tasks with `try/except: logger.exception(...)`. This is adequate. The improvement is ensuring these logged errors are queryable — structlog JSON format + log aggregation (see Observability section) makes them searchable by `request_id` or `thread_id`.

---

## Observability: Logging and Metrics

### Logging (no code change required for production)

The existing `configure_logging(production=True)` already produces JSON logs to stdout. Docker captures stdout automatically. The log format is already correct for Loki/Promtail ingestion.

**Add for full traceability**: The `RequestIDMiddleware` (see above) adds `request_id` to every log line within a request. Background task logs should bind `thread_id` via `structlog.contextvars.bind_contextvars(thread_id=inbound.thread_id)` at the start of `process_inbound_email()`.

### Metrics

`prometheus-fastapi-instrumentator` provides HTTP RED metrics out of the box at `/metrics`. No additional configuration needed for an MVP. Prometheus can be added as a third Docker Compose service later, or a hosted metrics service (Grafana Cloud free tier) can scrape the endpoint via a Grafana Agent running on the VM.

### Recommended observability stack for VM deployment

| Component | Approach | Why |
|-----------|---------|-----|
| Logs | structlog JSON stdout -> Docker log driver -> Loki via Grafana Agent | Zero-change to app; Grafana Agent runs as sidecar on VM |
| Metrics | `GET /metrics` -> Grafana Agent (Prometheus remote_write) -> Grafana Cloud | No Prometheus container needed on VM |
| Alerts | Grafana Cloud alert rules on error rate and negotiation state lag | Managed, no infra |

This is an MVP observability stack — no additional containers on the VM beyond Redis.

---

## Build Order: What to Implement First

The dependency graph for production readiness:

```
Step 1: Redis infrastructure (no code changes, just Docker config)
  ├── Add redis to docker-compose.yml
  └── Test redis container health check

Step 2: Redis client in services dict (app.py)
  ├── Add redis[asyncio] to pyproject.toml
  ├── initialize_services(): add redis_client init (step a.0)
  └── lifespan(): add redis_client.aclose() on shutdown

Step 3: Persist history_id to Redis (app.py)
  ├── lifespan(): read history_id from Redis at startup
  └── /webhooks/gmail: write history_id to Redis after each update
  (depends on Step 2)

Step 4: RedisThreadStateManager (new file + app.py wiring)
  ├── Create src/negotiation/slack/redis_takeover.py
  ├── initialize_services(): swap ThreadStateManager for RedisThreadStateManager
  └── Audit all async callers of claim_thread / is_human_managed
  (depends on Step 2)

Step 5: RedisNegotiationStateStore (new file + app.py wiring)
  ├── Create src/negotiation/state/redis_store.py
  ├── initialize_services(): swap negotiation_states dict for store
  ├── process_inbound_email(): await state_store.get() / set()
  └── start_negotiations_for_campaign(): await state_store.set()
  (depends on Step 2; serialization design decision must come first)

Step 6: Health endpoints (new file + create_app() wiring)
  ├── Create src/negotiation/health/endpoints.py
  ├── create_app(): include health router
  └── Dockerfile: add HEALTHCHECK instruction
  (depends on Step 2 for readiness check)

Step 7: Dockerfile + docker-compose.yml
  ├── Write Dockerfile
  ├── Write docker-compose.yml
  └── Test local build: docker compose up
  (depends on Steps 1-6 being functional)

Step 8: Prometheus metrics (create_app() modification)
  ├── Add prometheus-fastapi-instrumentator to pyproject.toml
  └── create_app(): add Instrumentator().instrument().expose()
  (can be done alongside Step 7)

Step 9: GitHub Actions workflow
  ├── Write .github/workflows/ci.yml
  ├── Set GitHub Secrets (VM_HOST, VM_USER, VM_SSH_KEY)
  └── Test: push to main, verify deploy
  (depends on Steps 7-8 producing a working Docker image)

Step 10: Request ID middleware + error handler
  ├── Add RequestIDMiddleware to create_app()
  └── Add global exception handler to create_app()
  (can be done at any point, zero dependencies)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Pickle for Redis State Serialization

**What:** Serialize `NegotiationStateMachine` objects with `pickle.dumps()` and store bytes in Redis.

**Why bad:** Pickle is a security risk if Redis is ever compromised (arbitrary code execution on deserialization). Pickle is also fragile when code changes — a pickled object from v1 code may fail to deserialize after refactoring `NegotiationStateMachine`. The class has only two fields: `_state` (StrEnum, serializes to str) and `_history` (list of tuples, serializes to JSON array of arrays). There is no reason to use pickle.

**Do instead:** Store `state_machine.state` (str) and `state_machine.history` (list) as JSON. Reconstruct on read.

### Anti-Pattern 2: Redis as Primary Audit Store

**What:** Move audit log writes from SQLite to Redis.

**Why bad:** Redis is ephemeral by nature even with AOF — it is a cache/session store, not an audit trail. SQLite with WAL mode on a named Docker volume provides ACID guarantees, full auditability, and SQL queryability. The audit trail is exactly what SQLite is good at.

**Do instead:** Keep SQLite for audit. Use Redis only for ephemeral session state (negotiation_states, thread_state, history_id) where the source of truth is eventually the email thread itself.

### Anti-Pattern 3: Separate Redis Connections per Request

**What:** Create a new `redis.asyncio.Redis` connection inside each request handler or each background task.

**Why bad:** Connection pool exhaustion under load. Redis connections are cheap but not free; creating one per request multiplied by concurrent negotiation background tasks can hit OS file descriptor limits.

**Do instead:** One `redis.asyncio.Redis` client initialized in `initialize_services()` stored in `services["redis_client"]`. The `redis-py` async client automatically manages a connection pool internally.

### Anti-Pattern 4: Blocking Redis Calls in Async Context

**What:** Use the synchronous `redis` client (not `redis.asyncio`) from within async FastAPI handlers.

**Why bad:** Blocks the event loop. Negotiation background tasks are already using `asyncio.to_thread` for synchronous Gmail calls — adding more blocking calls compounds latency.

**Do instead:** Use `redis.asyncio.Redis` (available in the `redis` package since version 4.2+). All calls are `await`-able.

### Anti-Pattern 5: Health Check That Always Returns 200

**What:** Keep the existing `/health` endpoint (`return {"status": "healthy"}`) as the Docker HEALTHCHECK target.

**Why bad:** A container that has lost its Redis connection or has a closed SQLite connection will appear healthy. Docker will never restart it. The team will discover the failure only when a negotiation silently fails.

**Do instead:** Use `/health/liveness` for Docker HEALTHCHECK (process alive check — no dep calls). Use `/health/readiness` for load balancer routing (dep checks). The existing `/health` endpoint can stay as-is for backward compatibility.

### Anti-Pattern 6: Storing Campaign Model Object in Redis

**What:** Serialize the full `Campaign` Pydantic model into Redis as part of negotiation state.

**Why bad:** The `Campaign` model is large and comes from ClickUp ingestion. It duplicates data that already exists in the audit log. Storing full models in Redis couples the session store to the business model schema — any field rename in `Campaign` requires a Redis migration.

**Do instead:** Store only `campaign_id` (string) in Redis negotiation state. If the full campaign is needed during email processing, it can be re-fetched from the audit log or passed through the existing `services` dict during the active request. In practice, `process_inbound_email()` only uses `context["campaign_id"]` for audit logging — it does not re-read the Campaign model.

---

## Scaling Considerations

| Concern | Single VM (current target) | Multi-VM future |
|---------|---------------------------|----------------|
| SQLite | Named volume, WAL mode, adequate for 100s of negotiations/day | Must migrate to PostgreSQL if multi-instance needed |
| Redis | Single Redis container with AOF | Redis Sentinel or Cluster for HA |
| Gmail Pub/Sub | Single process handles all notifications | Multiple instances would cause duplicate processing — needs deduplication in Redis |
| Slack Socket Mode | Runs in single thread via asyncio.to_thread | Socket Mode handles one connection per app token — naturally single instance |
| Anthropic API | 3-attempt retry already configured | Add circuit breaker if rate limits hit consistently |

**Conclusion**: The single VM + Docker Compose architecture is correct for the current scale. No Kubernetes needed. The architecture can scale to a Redis Sentinel setup or PostgreSQL migration as a later milestone.

---

## Sources

- FastAPI official documentation on Docker deployment: https://fastapi.tiangolo.com/deployment/docker/ (HIGH confidence)
- FastAPI official documentation on lifespan events: https://fastapi.tiangolo.com/advanced/events/ (HIGH confidence)
- Redis official documentation on Python client (redis-py async): https://redis.io/docs/latest/develop/clients/redis-py/ (HIGH confidence)
- Redis official documentation on persistence (AOF): https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/ (HIGH confidence)
- prometheus-fastapi-instrumentator GitHub: https://github.com/trallnag/prometheus-fastapi-instrumentator (MEDIUM confidence — verify current install pattern)
- appleboy/ssh-action GitHub: https://github.com/appleboy/ssh-action (HIGH confidence — use @v1 per 2025 release notes)
- SQLite WAL documentation: https://sqlite.org/wal.html (HIGH confidence)
- structlog JSON logging pattern: training data + verified against structlog docs in existing `app.py` implementation (HIGH confidence)
- GitHub Container Registry (GHCR): training data (HIGH confidence — stable GitHub product)

---

*Architecture research for: Influencer Negotiation Agent — Production Readiness Milestone*
*Researched: 2026-02-19*
*Focus: Integration points with existing FastAPI + services dict + SQLite architecture*
