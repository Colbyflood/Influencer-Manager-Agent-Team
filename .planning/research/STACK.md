# Stack Research — Production Readiness Additions

**Domain:** Production readiness additions for Python FastAPI negotiation agent
**Researched:** 2026-02-19
**Confidence:** HIGH (versions verified against PyPI live index; patterns verified against official docs and 2025-2026 articles)

---

## Context: What Already Exists (Do NOT Re-Add)

The following are already in `pyproject.toml` and working. This document covers ONLY new additions:

| Already Have | Version | Notes |
|---|---|---|
| Python | 3.12+ | Runtime |
| FastAPI | >=0.129.0 | HTTP framework |
| uvicorn | >=0.41.0 | ASGI server |
| Anthropic SDK | >=0.82.0 | LLM |
| structlog | >=25.5.0 | Structured logging (JSON mode already in app.py) |
| tenacity | >=9.1.4 | Retry with exponential backoff + jitter (already wraps external APIs) |
| SQLite (stdlib) | — | Audit trail (WAL mode, parameterized queries) |
| Pydantic v2 | >=2.12 | Data validation |
| httpx | >=0.28.1 | Async HTTP client |
| Gmail API client | >=2.190.0 | Email I/O |
| slack-bolt / slack-sdk | >=1.27.0 / >=3.40.1 | Slack integration |
| gspread | >=6.2.1 | Google Sheets |
| uv | — | Package manager |
| ruff | >=0.15 | Linter |
| pytest | >=9.0 | Test runner |
| pytest-cov | >=6.0 | Coverage |
| mypy | >=1.19 | Type checking |

The existing `resilience/retry.py` already implements tenacity-based retries with Slack error notification on final failure. Do not replace this pattern.

---

## New Stack Additions by Production Readiness Area

### 1. Persistent Negotiation State

**Problem:** `negotiation_states: dict[str, dict]` in `app.py` is lost on process restart. Negotiations span hours/days; a restart loses all in-flight state.

**Solution:** SQLAlchemy 2.0 async ORM with aiosqlite, same SQLite file as audit trail.

| Library | Version (verified PyPI) | Purpose | Why |
|---|---|---|---|
| `sqlalchemy[asyncio]` | 2.0.46 | Async ORM for persistent negotiation state | Industry standard async ORM. SQLite support via aiosqlite is production-quality since 2.0.38 added `AsyncAdaptedQueuePool` for file databases. Keeps the database on SQLite (no new infra) while adding async query API and schema migrations. |
| `aiosqlite` | 0.22.1 | Async SQLite driver for SQLAlchemy | Required async driver for `sqlite+aiosqlite://` engine. Runs SQLite on a dedicated thread, exposing async interface to the event loop. Zero infra cost — same SQLite file, different access pattern. |
| `alembic` | 1.18.4 | Schema migrations | Manages schema evolution for the new `negotiation_state` table. Required once SQLAlchemy ORM owns the schema. Use `batch_alter_table` for SQLite (SQLite cannot ALTER columns in place). |

**Integration:** The existing `data/audit.db` SQLite file already uses WAL mode (set in `audit/store.py`). The new negotiation state table goes into the same file. SQLAlchemy async engine connects to `sqlite+aiosqlite:///data/audit.db`.

**What NOT to use:** Do not introduce PostgreSQL for this milestone. It adds a new service dependency (container, credentials, backup), which conflicts with the goal of deploying a single-VM Docker container. SQLite with WAL mode handles the agent's concurrency (one writer per negotiation thread, serialized via asyncio).

---

### 2. Docker Deployment on Cloud VM

**Problem:** No Dockerfile, no container, no way to deploy to a VM.

**Solution:** Multi-stage Dockerfile + Docker Compose for local parity. No Kubernetes, no ECS — single VM target.

| Tool | Version | Purpose | Why |
|---|---|---|---|
| Docker | 27+ (engine) | Container runtime | Standard container runtime. Multi-stage build: builder stage installs deps with `uv`, runtime stage copies only the installed packages and source. |
| `python:3.12-slim` | latest slim | Base image | Slim variant over Alpine — Alpine uses musl libc which causes issues with some Python C extensions (google-api-python-client). 3.12-slim on Debian bullseye is safe and well-tested. |
| Docker Compose | v2 (plugin) | Local dev parity with production | Compose v2 (built into Docker) defines the full service (app + volume mount for SQLite file). Same file drives CI and VM deployment via `docker compose up -d`. |

**No new Python packages required.** Docker is infrastructure, not a Python dependency.

**Dockerfile pattern (multi-stage, uv-based):**
```dockerfile
# Stage 1: builder
FROM python:3.12-slim AS builder
RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: runtime
FROM python:3.12-slim
RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY src/ ./src/
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["python", "-m", "negotiation.app"]
```

**Volume mount for SQLite persistence:**
```yaml
# docker-compose.yml
volumes:
  - ./data:/app/data  # SQLite file survives container restarts
```

---

### 3. GitHub Actions CI/CD

**Problem:** No automated testing, linting, or deployment pipeline.

**Solution:** GitHub Actions with `astral-sh/setup-uv`, GHCR image push, SSH deploy to VM.

**No new Python packages.** CI/CD is YAML workflow configuration only.

**Workflow tools (all GitHub Actions, not Python libraries):**

| Action | Version | Purpose | Why |
|---|---|---|---|
| `astral-sh/setup-uv` | v6 | Install uv in CI | Official uv action. Built-in cache support keyed on `uv.lock`. Verified current from astral-sh/setup-uv GitHub. |
| `docker/login-action` | v3 | Authenticate to GHCR | Official Docker action. Logs in to `ghcr.io` using `GITHUB_TOKEN` (no extra secret needed). |
| `docker/build-push-action` | v6 | Build and push image | Official Docker action. Supports multi-stage builds, BuildKit cache, and multi-platform. |
| `docker/metadata-action` | v5 | Generate image tags | Generates semantic tags (branch name, commit SHA, semver) automatically. |

**CI pipeline stages:**
1. `lint` — `uv run ruff check . && uv run ruff format --check .`
2. `typecheck` — `uv run mypy src/`
3. `test` — `uv run pytest --cov=negotiation --cov-report=xml`
4. `build-push` — Build Docker image, push to GHCR (on main branch only)
5. `deploy` — SSH to VM, `docker compose pull && docker compose up -d` (on main branch only)

**Deploy step uses:** `appleboy/ssh-action` (SSH to VM). Secrets: `VM_HOST`, `VM_USER`, `VM_SSH_KEY` stored in GitHub repo secrets.

---

### 4. Monitoring and Alerting

**Problem:** No metrics endpoint, no error tracking beyond Slack notifications.

**Solution:** Prometheus metrics via FastAPI instrumentator + Sentry for error tracking. Structlog already handles structured logs.

| Library | Version (verified PyPI) | Purpose | Why |
|---|---|---|---|
| `prometheus-fastapi-instrumentator` | 7.1.0 | HTTP metrics (`/metrics` endpoint) | Adds Prometheus `http_requests_total`, `http_request_duration_seconds`, and response size metrics to FastAPI with two lines of code. Auto-instruments all routes. Composes with existing `Instrumentator().instrument(app).expose(app)` pattern. |
| `prometheus-client` | 0.24.1 | Custom business metrics | Needed for negotiation-specific counters (deals accepted, escalations triggered, emails sent). `prometheus-fastapi-instrumentator` depends on this — it will be installed transitively, but pin it explicitly for custom metrics. |
| `sentry-sdk` | 2.53.0 | Error tracking and performance monitoring | `sentry_sdk.init()` before FastAPI app creation auto-instruments FastAPI via `StarletteIntegration` and `FastApiIntegration`. Captures unhandled exceptions with full request context. Free tier sufficient for this scale. |
| `structlog-sentry` | 2.2.1 | Bridge structlog errors to Sentry | Adds `SentryProcessor` to structlog chain so `logger.error()` calls with `exc_info` are captured as Sentry events. Existing structlog config in `app.py` needs one processor added. Must be placed BEFORE `format_exc_info` processor in the chain. |

**What NOT to use:** Do not add Grafana, Loki, or Tempo to this milestone. Those require additional VM resources and operational complexity. Prometheus `/metrics` is sufficient — connect to a hosted Grafana Cloud free tier or defer dashboards to a later milestone.

**Integration point in `app.py`:**
```python
# After create_app():
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)  # Adds GET /metrics
```

```python
# In configure_logging(), add SentryProcessor before format_exc_info:
from structlog_sentry import SentryProcessor
shared_processors.insert(-1, SentryProcessor(level=logging.ERROR))
```

---

### 5. Error Handling and Retries (Enhancement)

**Problem:** `resilience/retry.py` already implements tenacity retries. What's missing is:
- Circuit breaker pattern to stop hammering APIs that are consistently down
- Dead letter logging for permanently failed negotiations

**Existing tenacity version:** 9.1.4 (already pinned in pyproject.toml — do not upgrade).

| Library | Version (verified PyPI) | Purpose | Why |
|---|---|---|---|
| No new library needed | — | Circuit breaker | Tenacity 9.x supports `stop_after_delay` and custom `retry` predicates. A circuit-breaker-like pattern can be implemented with `stop_after_attempt(3)` combined with Slack alerting (already done). True circuit breaker (open/half-open/closed states) is over-engineering for this scale. |

**What NOT to add:** `pybreaker` (adds complexity without payoff at this scale). The existing tenacity pattern + Slack alerting on final failure already covers the failure notification requirement.

**Enhancement to existing retry.py:** Add `wait_exponential_jitter` to idempotency keys for Gmail send operations — prevent duplicate sends if retry fires after a successful-but-timed-out Gmail API call.

---

### 6. Live Verification Testing

**Problem:** Integration tests mock all external APIs. Need a way to verify the live system works after deployment (smoke tests, health checks).

**Solution:** pytest-asyncio (upgrade) + pytest-httpx for endpoint verification. No live API calls in CI — tests use `TestClient` against the running app.

| Library | Version (verified PyPI) | Purpose | Why |
|---|---|---|---|
| `pytest-asyncio` | 1.3.0 | Async test support | Current project has 0.21.0 installed (per `pip index`). Version 1.x is a major release with changed default mode (no longer requires `@pytest.mark.asyncio` on every test if `asyncio_mode = "auto"` in config). Upgrade from 0.21.0 is a breaking change — update `pyproject.toml` to add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`. |
| `pytest-httpx` | 0.36.0 | Mock httpx calls in tests | Already using httpx for external HTTP calls. `pytest-httpx` provides `httpx_mock` fixture that intercepts httpx requests and asserts all registered responses were consumed. Catches regressions in external API call patterns. |
| `pydantic-settings` | 2.13.1 | Typed settings from env vars | Replaces the current `os.environ.get()` pattern in `app.py` with a `BaseSettings` class. Required for live verification — allows injecting test env vars cleanly without monkeypatching `os.environ`. Also adds `.env` file loading for the VM deployment. |

**What NOT to add:** Do not add actual live Gmail/Slack API calls to the CI test suite. Live verification means: the FastAPI app starts, `GET /health` returns 200, key endpoints accept correctly-shaped requests. External API calls are always mocked.

**Live smoke test pattern (post-deploy):**
```python
# tests/smoke/test_health.py — run against live VM after deploy
import httpx

def test_health_endpoint():
    resp = httpx.get("https://your-vm-host/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

---

## Complete New Dependencies to Add

```bash
# Persistent state
uv add "sqlalchemy[asyncio]>=2.0.46" "aiosqlite>=0.22.1" "alembic>=1.18.4"

# Monitoring
uv add "prometheus-fastapi-instrumentator>=7.1.0" "prometheus-client>=0.24.1"
uv add "sentry-sdk>=2.53.0" "structlog-sentry>=2.2.1"

# Settings management
uv add "pydantic-settings>=2.13.1"

# Dev / test additions
uv add --dev "pytest-asyncio>=1.3.0" "pytest-httpx>=0.36.0"
```

**pyproject.toml additions:**
```toml
[tool.pytest.ini_options]
# Add to existing options:
asyncio_mode = "auto"  # Required for pytest-asyncio 1.x

[tool.pytest.ini_options]
# Existing: testpaths = ["tests"]
# Existing: pythonpath = ["src"]
# Existing: addopts = "-v --tb=short"
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not Alternative |
|---|---|---|
| SQLite + aiosqlite (persistent state) | PostgreSQL | Adds a second service to the Docker compose stack, requires connection pooling config, backup strategy, and credentials management. SQLite with WAL mode handles this agent's concurrency — one asyncio event loop, serialized writes per negotiation. Revisit if multiple VM instances are ever needed. |
| SQLite + aiosqlite (persistent state) | Redis | Redis is volatile by default (requires persistence config), adds another service, and is over-engineered for the state size (dozens of concurrent negotiations at most). |
| `prometheus-fastapi-instrumentator` | OpenTelemetry | OTEL is the right long-term direction but requires a collector sidecar and significantly more configuration. `prometheus-fastapi-instrumentator` is two lines of code and produces metrics immediately compatible with Grafana Cloud. |
| GHCR (GitHub Container Registry) | Docker Hub | GHCR is free for public repos and uses `GITHUB_TOKEN` (no additional secrets). Docker Hub has pull rate limits that can break CI. |
| `pydantic-settings` | `python-dotenv` alone | `pydantic-settings` gives type-validated, documented settings with IDE support. `python-dotenv` just loads .env into `os.environ` — still requires manual `os.environ.get()` calls with no validation. `pydantic-settings` uses `python-dotenv` internally when `env_file` is set. |
| `pytest-asyncio` 1.3.0 | Stay on 0.21.0 | 1.x removes the need to mark every async test individually (`asyncio_mode = "auto"`). The codebase will grow significantly more async tests in this milestone — the upgrade pays off. |
| Sentry (hosted) | Self-hosted error tracking | Self-hosted Sentry is a multi-container deployment. The free tier of sentry.io handles this scale with no infra burden. |

---

## What NOT to Add (Production Anti-Patterns for This Scale)

| Avoid | Why | Use Instead |
|---|---|---|
| PostgreSQL | Adds infra complexity (container, credentials, backups) that SQLite with WAL mode doesn't need at this scale | SQLite + aiosqlite + alembic |
| Redis / Celery | Task queue overkill for an agent with asyncio background tasks already implemented | `asyncio.ensure_future()` (already used in `app.py`) |
| Kubernetes / ECS | Over-engineered for single-VM deployment target | Docker Compose + single VM |
| Grafana / Loki (self-hosted) | Requires 3+ additional containers (Prometheus, Grafana, Loki, Promtail) | Prometheus `/metrics` + Grafana Cloud free tier |
| OpenTelemetry | Requires collector sidecar, significantly more config | `prometheus-fastapi-instrumentator` for metrics, Sentry for traces |
| `gunicorn` as process manager | Gunicorn + Uvicorn worker pattern is correct for multi-core, but the Slack Bolt Socket Mode handler runs in a thread via `asyncio.to_thread` — gunicorn's forking model breaks this pattern | Single `uvicorn` process (already works; add `--workers 1` explicitly) |
| `langchain` / `langgraph` | The agent already uses raw Anthropic SDK + custom state machine. LangGraph would require migrating the entire negotiation loop. Adds 50+ MB of dependencies for no new capability | Existing `NegotiationStateMachine` + `resilience/retry.py` |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---|---|---|
| `sqlalchemy[asyncio]` 2.0.46 | `aiosqlite` 0.22.1 | SQLAlchemy 2.0.38+ uses `AsyncAdaptedQueuePool` for file SQLite — aiosqlite 0.22.x is the correct companion. |
| `alembic` 1.18.4 | `sqlalchemy` 2.0.46 | Alembic 1.18.x targets SQLAlchemy 2.x. Use `batch_alter_table` for all SQLite schema changes. |
| `prometheus-fastapi-instrumentator` 7.1.0 | `fastapi` >=0.129.0, `prometheus-client` 0.24.1 | PFI 7.x requires prometheus-client 0.19+. FastAPI version constraint is met. |
| `sentry-sdk` 2.53.0 | `fastapi` >=0.129.0 | Sentry 2.x auto-detects FastAPI via `StarletteIntegration`. Initialize Sentry BEFORE creating the FastAPI app instance. |
| `structlog-sentry` 2.2.1 | `structlog` >=25.5.0, `sentry-sdk` >=2.0 | `SentryProcessor` must be added to structlog chain BEFORE `format_exc_info` to capture exception context. |
| `pytest-asyncio` 1.3.0 | `pytest` >=9.0 | 1.x requires `asyncio_mode = "auto"` in `[tool.pytest.ini_options]` or `asyncio_mode = "strict"` with explicit markers. Breaking change from 0.21.0. |
| `pytest-httpx` 0.36.0 | `httpx` >=0.28.1 | pytest-httpx must match the httpx version installed. 0.36.x targets httpx 0.28.x which is already pinned. |
| `pydantic-settings` 2.13.1 | `pydantic` >=2.12 | pydantic-settings 2.x requires pydantic v2. Already have pydantic v2. |

---

## Environment Variables (New for Production)

```bash
# Sentry (get DSN from sentry.io after creating project)
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production  # or "staging", "development"
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of requests traced (cost control)

# SQLite persistent state (extends existing AUDIT_DB_PATH)
# No new env var needed — negotiation_state table goes in the same DB file
# AUDIT_DB_PATH=data/audit.db  (already exists)

# Production mode (already used in app.py for structlog JSON rendering)
PRODUCTION=true

# Health check (no new var — app.py reads WEBHOOK_PORT)
# WEBHOOK_PORT=8000  (already exists)
```

---

## Sources

- **SQLAlchemy 2.0.46 version:** `pip index versions sqlalchemy` — verified 2026-02-19. HIGH confidence.
- **aiosqlite 0.22.1 version:** `pip index versions aiosqlite` — verified 2026-02-19. HIGH confidence.
- **SQLAlchemy async SQLite `AsyncAdaptedQueuePool`:** [SQLAlchemy 2.0 docs asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), changelog note for 2.0.38. HIGH confidence.
- **alembic 1.18.4 version:** `pip index versions alembic` — verified 2026-02-19. HIGH confidence.
- **prometheus-fastapi-instrumentator 7.1.0:** `pip index versions prometheus-fastapi-instrumentator` + [PyPI](https://pypi.org/project/prometheus-fastapi-instrumentator/). HIGH confidence.
- **prometheus-client 0.24.1:** `pip index versions prometheus-client` — verified 2026-02-19. HIGH confidence.
- **sentry-sdk 2.53.0:** `pip index versions sentry-sdk` — verified 2026-02-19. [Sentry FastAPI docs](https://docs.sentry.io/platforms/python/integrations/fastapi/). HIGH confidence.
- **structlog-sentry 2.2.1:** `pip index versions structlog-sentry` — verified 2026-02-19. [kiwicom/structlog-sentry](https://github.com/kiwicom/structlog-sentry). HIGH confidence.
- **pydantic-settings 2.13.1:** `pip index versions pydantic-settings` — verified 2026-02-19. [Pydantic Settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). HIGH confidence.
- **pytest-asyncio 1.3.0:** `pip index versions pytest-asyncio` — verified 2026-02-19. HIGH confidence.
- **pytest-httpx 0.36.0:** `pip index versions pytest-httpx` — verified 2026-02-19. HIGH confidence.
- **astral-sh/setup-uv GitHub Actions:** [Official docs](https://docs.astral.sh/uv/guides/integration/github/) + [GitHub Marketplace](https://github.com/marketplace/actions/astral-sh-setup-uv). HIGH confidence.
- **Docker multi-stage with uv:** [Mastering uv Part 4](https://bury-thomas.medium.com/mastering-python-project-management-with-uv-part-4-ci-cd-docker-ed4128fdd0c1), [FastAPI Docker Best Practices](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/). MEDIUM confidence (pattern validated across multiple 2025 sources).
- **`gunicorn` incompatibility with Slack Bolt Socket Mode:** Training data + Socket Mode docs (asyncio.to_thread pattern in existing app.py confirms single-process requirement). MEDIUM confidence.

---

*Stack research for: Production readiness additions — influencer negotiation agent*
*Researched: 2026-02-19*
*Scope: NEW additions only. Existing stack (FastAPI, SQLite stdlib, structlog, tenacity, etc.) documented in context but not re-researched.*
