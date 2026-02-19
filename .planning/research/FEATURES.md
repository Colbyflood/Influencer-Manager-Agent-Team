# Feature Research: Production Readiness for Influencer Negotiation Agent

**Domain:** Production readiness for a FastAPI negotiation agent (persistent state, deployment, CI/CD, monitoring, live integration testing)
**Researched:** 2026-02-19
**Confidence:** HIGH for infrastructure patterns (well-established, verified via web search 2025/2026 sources); MEDIUM for SQLite-specific state persistence trade-offs (fewer canonical sources)

---

## Context: What Is Already Built

The v1.0 negotiation agent is feature-complete for negotiation logic. What it lacks is production-grade infrastructure:

- **In-memory negotiation state** (`negotiation_states: dict`) — lost on every restart or deploy
- **No Docker packaging** — runs only locally via `uvicorn` directly
- **No CI/CD pipeline** — no automated test or deploy on push
- **No health check endpoints** — Docker/load balancer cannot verify liveness or readiness
- **No monitoring/alerting** — structured logging (structlog) is wired, but no external observability
- **Retry logic exists** (`tenacity` decorator in `resilience/retry.py`) but is not applied consistently
- **No live integration tests** — 691 unit tests all use mocks; no real Gmail/Sheets/Slack calls verified

---

## Feature Landscape

### Table Stakes (Operators Expect These)

Features any production-deployed service must have. Missing = service is not deployable or not trustworthy.

| Feature | Why Expected | Complexity | Depends On |
|---------|--------------|------------|------------|
| **Persistent negotiation state** | In-memory dict is lost on restart; active negotiations mid-thread would be silently dropped with no recovery | MEDIUM | SQLite already present (audit trail); extend same DB or add table |
| **Docker container packaging** | Cloud VM deployment requires a container image; also enforces reproducible environment parity | MEDIUM | None — greenfield addition |
| **Docker Compose for local + production** | Defines the full runtime stack (app + volume mounts) in one file; enables one-command startup | LOW | Docker container |
| **`/health` liveness endpoint** | Docker `HEALTHCHECK`, cloud VM health probes, and load balancers require a fast liveness signal | LOW | FastAPI already running |
| **`/ready` readiness endpoint** | Checks that all critical dependencies (Gmail token valid, audit DB writable) are actually functional before routing live traffic | MEDIUM | Health infrastructure pattern |
| **GitHub Actions CI workflow** | On every push: run 691 tests, lint with ruff, type-check with mypy — catches regressions before they reach production | LOW | None; project already has ruff + mypy configured |
| **GitHub Actions CD workflow** | On merge to main: build Docker image, push to registry, SSH deploy to cloud VM | MEDIUM | CI passing, Docker image |
| **Structured JSON logging in production** | `structlog` is configured for JSON in production mode already (`PRODUCTION=1`); just needs the env var set correctly in container | LOW | Already coded; just env config |
| **Secret management via env vars** | API keys (Anthropic, Gmail token, Slack) must not be in Docker images; must come from environment or secrets manager | LOW | Already uses `os.environ`; needs `.env` file excluded from image |
| **Graceful shutdown** | SIGTERM from Docker/process manager must complete in-flight email processing before dying; uvicorn handles this but must be configured | LOW | Already using uvicorn; configure timeout |
| **State recovery after crash** | If process dies with an active negotiation, the negotiation_states dict is gone; need to identify orphaned threads on startup | HIGH | Persistent state must exist first |

### Differentiators (Production Quality Upgrades)

Features that lift the agent from "works on my machine" to genuinely robust. Not blockers but matter for reliability.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **SQLite state persistence (not PostgreSQL)** | Persists negotiation state to SQLite alongside the existing audit trail — zero new infrastructure; survives restarts without a separate database service | LOW | SQLite is already present and working; add a `negotiation_states` table; acceptable at this scale since SQLite is single-writer and negotiations are not concurrent-write heavy |
| **Multi-stage Docker build with uv** | Smaller image (200MB vs 1GB+), faster deploys, non-root runtime user — security and operational improvement | MEDIUM | Uses `uv` already in dev; extend to Docker image |
| **Retry decorator applied consistently** | `resilient_api_call` decorator exists but is not applied to GmailClient, SheetsClient, and Anthropic calls systematically | LOW | Extend existing pattern; no new libraries |
| **Circuit breaker for Anthropic API** | If LLM is down, negotiations should queue (not fail silently or lose work); circuit breaker prevents cascade | MEDIUM | `tenacity` already present; add circuit open/closed state |
| **Gmail watch auto-renewal on startup** | Already coded (`renew_gmail_watch_periodically`) but needs to be verified and tested end-to-end after deploy | LOW | Already implemented; needs live test |
| **`@pytest.mark.live` integration tests** | Pytest marker that skips real Gmail/Sheets/Slack calls in CI (no credentials) but runs locally when credentials are present | MEDIUM | Requires real test account credentials |
| **Startup validation checks** | On app boot, verify each configured service is reachable: Gmail token valid, Slack token valid, Sheets key set — fail fast with clear errors | LOW | Add to lifespan context manager |
| **Audit DB as health signal** | `/ready` endpoint checks audit DB is writable (not just open) — catches disk-full or permission errors before serving traffic | LOW | Already have `init_audit_db` and `close_audit_db` |
| **Docker volume for SQLite persistence** | SQLite files inside the container are destroyed on redeploy; mount a persistent volume for `data/` directory | LOW | Docker Compose volume mount |
| **Env-based feature flags** | Allow disabling individual integrations (e.g., `GMAIL_ENABLED=false`) without code changes for development or partial deploys | LOW | Pattern already used for service initialization |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem like natural next steps but create real problems for this milestone.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **PostgreSQL for state persistence** | "SQLite doesn't scale" | This agent runs on a single VM, has at most dozens of concurrent negotiations, and already uses SQLite for the audit trail successfully. Adding PostgreSQL means a new service, connection pooling, `asyncpg`, Alembic migrations — weeks of work for zero real benefit at this scale. | Stay on SQLite. The audit trail proves it works. Add a `negotiation_states` table. Revisit if the agent ever runs on multiple hosts. |
| **Redis for in-memory caching** | "Cache Gmail tokens / rate limit tracking" | Redis is another service to run, configure, and monitor. Gmail tokens are refreshed infrequently and OAuth handles expiry. Rate limiting is not a current bottleneck. | Tenacity retry with backoff handles transient failures. Token refresh is built into the Google auth library. Skip Redis entirely for v1.1. |
| **Kubernetes / ECS deployment** | "Containers should run in an orchestrator" | This agent runs on one cloud VM. Kubernetes adds enormous operational overhead (ingress, node groups, pod scheduling, service mesh) that far exceeds the needs of a single-process agent. | Docker with Docker Compose on a VM is correct for this scale. If the agent ever needs horizontal scaling or zero-downtime rolling deploys, revisit. |
| **Prometheus + Grafana monitoring stack** | "We need metrics dashboards" | A two-service monitoring stack (Prometheus scraper + Grafana dashboard) is significant infrastructure for a single-VM single-process agent. Also requires persistent storage for metrics. | Structured JSON logs from structlog can be queried with simple tools. If a dashboard is ever needed, use a hosted service (Datadog, Betterstack) that ingests structured logs without running new infrastructure. |
| **Full observability traces (OpenTelemetry)** | "We should trace every request" | Distributed tracing is for distributed systems. This is a single-process agent. Adding OpenTelemetry instrumentation without a trace backend is noise; adding a trace backend is more infrastructure. | Structured contextual logging with `negotiation_id`, `thread_id`, `campaign_id` bound to every log line already provides tracing within a single process. |
| **Parallel pytest-asyncio for integration tests** | "Run all live tests at once" | Real Gmail/Sheets/Slack calls need rate limits, ordered setup/teardown, and real API quotas. Parallel live tests will hit rate limits and interfere with each other. | Sequential pytest with `@pytest.mark.live` marker. One live test per integration point, run one at a time. |
| **Auto-deploy on every commit to main** | "Full CD means deploy on every merge" | The agent sends real emails and manages real negotiations. A bad deploy that breaks email sending could drop mid-negotiation threads. | CI on every push; CD on explicit tag or manual approval step. Or deploy only when all live integration tests pass. |
| **Hot reload in production (watchfiles)** | "Faster iteration with live reload" | Hot reload in production means unreliable state — the in-memory `negotiation_states` dict is cleared on every reload. In development it's fine; in production it causes silent negotiation drops. | Production uses a fixed container image. Development uses `--reload` locally only. |

---

## Feature Dependencies

```
[Persistent Negotiation State]
    |-- requires --> [SQLite state table schema]
    |-- requires --> [State serialization / deserialization]
    |-- enables  --> [State recovery after crash]
    |-- enables  --> [/ready endpoint: state DB writable check]

[Docker Container]
    |-- requires --> [Multi-stage Dockerfile with uv]
    |-- requires --> [Secret env var management (no secrets in image)]
    |-- requires --> [Docker volume for SQLite data/]
    |-- enables  --> [/health liveness endpoint (Docker HEALTHCHECK)]
    |-- enables  --> [/ready readiness endpoint]

[GitHub Actions CI]
    |-- requires --> [Docker container (build step)]
    |-- requires --> [pyproject.toml dev deps: pytest, ruff, mypy]
    |-- enables  --> [GitHub Actions CD (only deploy after CI passes)]

[GitHub Actions CD]
    |-- requires --> [GitHub Actions CI passing]
    |-- requires --> [Docker image pushed to registry]
    |-- enables  --> [SSH-based VM deploy]

[/health endpoint]
    |-- requires --> [FastAPI app running]
    |-- enables  --> [Docker HEALTHCHECK directive]

[/ready endpoint]
    |-- requires --> [/health endpoint (separate concern)]
    |-- requires --> [Persistent state (audit DB writable check)]
    |-- enables  --> [Pre-traffic validation in CI]

[@pytest.mark.live integration tests]
    |-- requires --> [Real credential files available (not in CI)]
    |-- requires --> [/ready endpoint (confirm system is actually live)]
    |-- enables  --> [Post-deploy smoke test: real email round trip]

[Retry decorator applied consistently]
    |-- requires --> [resilient_api_call already exists]
    |-- enables  --> [Graceful degradation: Gmail down -> queue, not crash]

[Startup validation checks]
    |-- requires --> [Lifespan context manager already exists]
    |-- enables  --> [Fast failure: bad credential caught at boot, not mid-negotiation]
```

### Dependency Notes

- **Persistent state is the highest-risk item:** Everything else (Docker, CI, health checks) is standard plumbing. State migration from in-memory dict to SQLite requires careful design of the serialization layer — what does a `NegotiationStateMachine` look like as a table row?
- **Health endpoints are a prerequisite for Docker deployment:** Docker `HEALTHCHECK` will not work without them. Build these before the Dockerfile.
- **CI must pass before CD is wired:** Never wire auto-deploy to a broken CI. Build CI first, validate it runs clean, then add the deploy step.
- **Live integration tests are independent of CI:** They run locally with real credentials. They should NOT run in GitHub Actions (no credentials there). The marker pattern (`@pytest.mark.live`) enforces this cleanly.

---

## MVP Definition

### Launch With (v1.1 — Production Readiness)

Minimum needed to deploy the agent to a cloud VM and trust that negotiations survive restarts.

- [ ] **Persistent negotiation state in SQLite** — without this, any deploy or crash drops active negotiations; it is the entire point of this milestone
- [ ] **State recovery on startup** — on boot, load all non-terminal negotiations from DB back into `negotiation_states` dict
- [ ] **`/health` liveness endpoint** — returns 200 if process is alive; Docker HEALTHCHECK uses this
- [ ] **`/ready` readiness endpoint** — checks audit DB writable, Gmail token present, returns 503 if not ready
- [ ] **Multi-stage Dockerfile** — `uv`-based build, non-root user, copies only runtime artifacts
- [ ] **Docker Compose file** — defines app service + named volume for `data/` persistence
- [ ] **GitHub Actions CI** — on push: `pytest`, `ruff check`, `mypy`; blocks merge on failure
- [ ] **GitHub Actions CD** — on tag or manual trigger: build image, push to registry, SSH deploy
- [ ] **Secret management** — `.env.example` template; secrets passed as env vars, never baked into image
- [ ] **Graceful shutdown** — uvicorn configured with appropriate signal handling; in-flight requests complete

### Add After Initial Deploy (v1.1.x)

Features to add once the agent is running live and processing real negotiations.

- [ ] **`@pytest.mark.live` integration tests** — trigger: agent is deployed and real credentials are available for a test run
- [ ] **Retry decorator applied to GmailClient and SheetsClient** — trigger: first time a Gmail API transient error drops a negotiation
- [ ] **Startup validation checks** — trigger: a bad credential causes a confusing mid-runtime failure instead of a clear boot error
- [ ] **Circuit breaker for Anthropic API** — trigger: LLM API outage causes negotiation processing failures

### Future Consideration (v2+)

Features to defer until there is evidence they are needed.

- [ ] **PostgreSQL migration** — defer: only if agent runs on multiple hosts; SQLite is sufficient for one VM
- [ ] **Redis task queue** — defer: only if email processing volume exceeds what asyncio background tasks handle
- [ ] **Hosted log aggregation (Datadog/Betterstack)** — defer: only when structured logs need cross-session search
- [ ] **OpenTelemetry traces** — defer: only when the agent expands to multi-service architecture

---

## Feature Prioritization Matrix

| Feature | Operator Value | Implementation Cost | Priority |
|---------|---------------|---------------------|----------|
| Persistent negotiation state in SQLite | HIGH | MEDIUM | P1 |
| State recovery on startup | HIGH | MEDIUM | P1 |
| `/health` liveness endpoint | HIGH | LOW | P1 |
| `/ready` readiness endpoint | HIGH | LOW | P1 |
| Multi-stage Dockerfile | HIGH | MEDIUM | P1 |
| Docker Compose file | HIGH | LOW | P1 |
| GitHub Actions CI | HIGH | LOW | P1 |
| GitHub Actions CD | HIGH | MEDIUM | P1 |
| Secret management pattern | HIGH | LOW | P1 |
| Graceful shutdown | MEDIUM | LOW | P1 |
| `@pytest.mark.live` integration tests | HIGH | MEDIUM | P2 |
| Retry decorator applied consistently | MEDIUM | LOW | P2 |
| Startup validation checks | MEDIUM | LOW | P2 |
| Circuit breaker for Anthropic | LOW | MEDIUM | P3 |
| PostgreSQL migration | LOW | HIGH | P3 |
| Redis task queue | LOW | HIGH | P3 |

**Priority key:**
- P1: Required to deploy and trust the agent in production
- P2: Adds reliability; add after first live deploy
- P3: Premature optimization; defer until evidence of need

---

## Detailed Feature Notes

### Persistent Negotiation State

**The core challenge:** `negotiation_states: dict[str, dict[str, Any]]` in `app.py` (line 236) holds all active negotiation context in process memory. Any restart, crash, or deploy clears it. Threads that receive a reply after a restart will be silently ignored (`No active negotiation for thread, ignoring`).

**What needs to be serialized per negotiation:**
- `NegotiationStateMachine` state + history (state enum + list of `(from, event, to)` tuples)
- `context` dict: influencer name/email, thread_id, platform, average_views, deliverables, CPM range, campaign_id
- `round_count` integer
- `campaign` model reference (by campaign_id, not object)
- `cpm_tracker` state (target_min, target_max, current achieved CPM per influencer)

**Recommended approach:** Add a `negotiation_states` table to the existing SQLite audit DB. Serialize context as JSON. State machine state stored as the enum value string. On startup, `initialize_services` queries all non-terminal rows and repopulates the dict. This requires minimal new infrastructure since the audit DB connection already exists.

**Confidence:** HIGH — SQLite with JSON columns for semi-structured context is a proven pattern. The audit DB already opens a connection at startup and closes it at shutdown.

### Health Check Endpoints

**`/health` (liveness):** Returns `{"status": "ok"}` with HTTP 200. Must be fast (< 100ms). No external calls. Just confirms the process is alive. Used by Docker `HEALTHCHECK`.

**`/ready` (readiness):** Checks:
1. Audit DB is writable (attempt a lightweight write, roll back)
2. Gmail token file exists at `GMAIL_TOKEN_PATH` (if Gmail is configured)
3. Anthropic API key is set (does not make an API call)
Returns `{"status": "ok", "checks": {...}}` with HTTP 200, or `{"status": "degraded", "checks": {...}}` with HTTP 503.

**Confidence:** HIGH — pattern verified in multiple 2025 FastAPI production guides; the distinction between liveness and readiness is universally recommended.

### Docker Build Strategy

**Multi-stage with uv:**
```
Stage 1 (builder): python:3.12-slim + uv install + uv sync (install all deps)
Stage 2 (runtime): python:3.12-slim + copy .venv from builder + run as non-root user
```

**Key decisions:**
- Non-root user (`USER app`) — prevents container escape escalation
- `.dockerignore` excludes `.venv/`, `tests/`, `.git/`, credential files
- `data/` directory is a Docker named volume — survives container replacement
- `HEALTHCHECK` in Dockerfile calls `/health` every 30s with 3 retries

**Confidence:** HIGH — multi-stage uv-based Docker builds are documented in official uv docs and multiple 2025 guides.

### GitHub Actions CI

**Trigger:** Push to any branch, PR to main.

**Steps:**
1. Checkout + set up Python 3.12
2. Install uv, run `uv sync --group dev`
3. `ruff check src/ tests/`
4. `mypy src/`
5. `pytest tests/ -x --tb=short` (fail fast on first failure)

**No live credentials in CI.** Tests with `@pytest.mark.live` are skipped automatically because credential env vars are not set.

**Confidence:** HIGH — standard GitHub Actions pattern; project already has ruff, mypy, pytest configured in `pyproject.toml`.

### GitHub Actions CD

**Trigger:** Manual workflow dispatch OR push of a version tag (`v*.*.*`).

**Steps:**
1. CI must pass (dependency on CI workflow)
2. Build Docker image with tag matching the version/SHA
3. Push to container registry (GitHub Container Registry / GHCR is free with GitHub repos)
4. SSH to cloud VM, pull new image, restart container

**Rationale for manual/tag trigger:** The agent sends real emails. An automatic deploy on every merge is too aggressive for a system managing live negotiations. A human should consciously trigger production deploys.

**Confidence:** HIGH — SSH-based VM deploy via GitHub Actions is well-documented; GHCR integration is native to GitHub.

### Live Integration Tests

**Pattern:** `@pytest.mark.live` custom marker. Any test marked as live is skipped unless `LIVE_TEST_MODE=1` env var is set.

```python
# tests/conftest.py
import pytest
import os

def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as requiring real API credentials")

def pytest_collection_modifyitems(config, items):
    if not os.environ.get("LIVE_TEST_MODE"):
        skip_live = pytest.mark.skip(reason="Set LIVE_TEST_MODE=1 to run live tests")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)
```

**What live tests cover:**
1. Gmail: send a test email to a test inbox, confirm it appears in Gmail Sent
2. Gmail: trigger a Pub/Sub notification, confirm the webhook handler receives it
3. Sheets: read a known row from the test spreadsheet, confirm data structure
4. Slack: post a test message to the dev channel, confirm message ID returned
5. End-to-end: trigger a ClickUp webhook with a test campaign, verify negotiation state is persisted

**Run frequency:** Not in CI. Run locally by a developer before a production release, or after a deploy to verify the live system is working.

**Confidence:** MEDIUM — the pytest marker skip pattern is standard (verified in pytest docs); the specific test content for Gmail/Slack is derived from training data patterns.

---

## Sources

- FastAPI health check patterns: [FastAPI Health Checks and Timeouts](https://medium.com/@bhagyarana80/fastapi-health-checks-and-timeouts-avoiding-zombie-containers-in-production-411a27c2a019) — MEDIUM confidence (2025)
- Docker multi-stage builds with uv: [Build Multistage Python Docker Images Using UV](https://digon.io/en/blog/2025_07_28_python_docker_images_with_uv) — MEDIUM confidence (2025)
- FastAPI Docker best practices: [FastAPI Docker Best Practices](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/) — MEDIUM confidence (2025)
- GitHub Actions CI/CD for FastAPI: [PyImageSearch FastAPI CI/CD](https://pyimagesearch.com/2024/11/04/enhancing-github-actions-ci-for-fastapi-build-test-and-publish/) — MEDIUM confidence (2024)
- FastAPI in-memory state persistence: [Persisting memory state between requests in FastAPI](https://github.com/fastapi/fastapi/issues/5045) — MEDIUM confidence
- SQLite with FastAPI: [FastAPI tutorial: SQL Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/) — HIGH confidence (official docs)
- Graceful degradation patterns: [Building Resilient REST API Integrations](https://medium.com/@oshiryaeva/building-resilient-rest-api-integrations-graceful-degradation-and-combining-patterns-e8352d8e29c0) — MEDIUM confidence (Jan 2026)
- Circuit breaker patterns for FastAPI: [FastAPI Circuit Breakers](https://medium.com/@kaushalsinh73/fastapi-circuit-breakers-with-resilience-patterns-surviving-downstream-failures-4af0920799d3) — MEDIUM confidence (Dec 2025)
- pytest markers and skipping: [pytest docs: custom markers](https://docs.pytest.org/en/stable/example/markers.html) — HIGH confidence (official docs)
- FastAPI production deployment guide: [FastAPI Deployment Guide 2026](https://www.zestminds.com/blog/fastapi-deployment-guide/) — LOW confidence (marketing site, 2026)
- Current codebase analysis: `src/negotiation/app.py`, `src/negotiation/resilience/retry.py`, `pyproject.toml` — HIGH confidence (read directly)

---
*Feature research for: Production readiness — Influencer Negotiation Agent v1.1*
*Researched: 2026-02-19*
*Scope: NEW features only — v1.0 negotiation features already built and shipped*
