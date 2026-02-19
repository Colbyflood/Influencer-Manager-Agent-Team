# Project Research Summary

**Project:** Influencer Negotiation Agent -- v1.1 Production Readiness
**Domain:** Production hardening for existing Python/FastAPI AI agent (Docker, persistent state, CI/CD, monitoring, health checks, live verification)
**Researched:** 2026-02-19
**Confidence:** HIGH

## Executive Summary

The Influencer Negotiation Agent is a working 6,799 LOC FastAPI application that automates influencer rate negotiation via email. The v1.0 agent is feature-complete for negotiation logic (691 tests passing), but runs only locally with all state held in a Python dict that is lost on every restart. The v1.1 milestone makes this agent production-deployable: persistent negotiation state, Docker packaging, CI/CD pipeline, health checks, monitoring, and live verification. The research across all four areas converges on a clear conclusion: this is standard production hardening for a single-VM single-process service, with one high-risk element (state persistence migration) and otherwise well-established patterns.

The recommended approach is conservative: stay on SQLite for persistent state (extending the existing audit database rather than adding new infrastructure), package in Docker with a multi-stage uv-based build, deploy to a single VM via GitHub Actions CI/CD with SSH, add Prometheus metrics and Sentry error tracking for observability, and implement liveness/readiness health endpoints. The research explicitly rejects PostgreSQL, Redis, Kubernetes, and self-hosted monitoring stacks as over-engineering for the current scale (single VM, dozens of concurrent negotiations, one asyncio event loop). Every recommendation preserves the existing architecture and adds the minimum new infrastructure to make it production-viable.

The key risks are: (1) OAuth credential files not surviving container restarts -- solved by Docker volume mounts and startup validation, (2) the in-memory `negotiation_states` dict being lost on deploy or crash -- solved by SQLite persistence with write-on-every-transition, (3) Gmail Pub/Sub watch expiration after container restarts -- solved by persisting the watch expiration timestamp, and (4) the Slack Bolt synchronous Socket Mode handler deadlocking or crashing the container -- which requires monitoring and eventual migration to async Bolt. All four pitfalls have clear prevention strategies that are addressed in the recommended phase structure below.

## Key Findings

### Recommended Stack

The stack research verified all package versions against PyPI on 2026-02-19. No new infrastructure services are introduced -- only Python libraries and Docker tooling. The additions break down into six areas: persistent state (SQLAlchemy async + aiosqlite + Alembic), Docker deployment (multi-stage Dockerfile + Docker Compose), CI/CD (GitHub Actions with astral-sh/setup-uv), monitoring (prometheus-fastapi-instrumentator + Sentry), settings management (pydantic-settings), and test tooling (pytest-asyncio 1.3.0 + pytest-httpx).

**Core technologies (new additions only):**
- **SQLAlchemy 2.0.46 (async) + aiosqlite 0.22.1:** Persistent negotiation state in the existing SQLite audit DB -- zero new infrastructure, same database file, async query API
- **Alembic 1.18.4:** Schema migrations for the new negotiation_states table -- required for SQLAlchemy ORM; must use `batch_alter_table` for SQLite
- **prometheus-fastapi-instrumentator 7.1.0:** HTTP metrics at `/metrics` with two lines of code -- immediate Prometheus compatibility
- **Sentry SDK 2.53.0 + structlog-sentry 2.2.1:** Error tracking with full request context; bridges existing structlog pipeline to Sentry
- **pydantic-settings 2.13.1:** Typed, validated settings from env vars and `.env` files -- replaces raw `os.environ.get()` calls
- **Docker 27+ with python:3.12-slim:** Multi-stage build using uv; non-root runtime user; HEALTHCHECK directive
- **GitHub Actions:** astral-sh/setup-uv v6 for CI, docker/build-push-action v6 for GHCR image push, appleboy/ssh-action for VM deploy

**Explicitly rejected (with rationale):**
- PostgreSQL (adds a second service for no benefit at this scale)
- Redis (volatile by default, over-engineered for dozens of concurrent negotiations)
- Kubernetes/ECS (massive operational overhead for a single-VM target)
- OpenTelemetry (requires a collector sidecar; Prometheus metrics + Sentry covers the need)
- gunicorn (forking model breaks Slack Bolt Socket Mode's `asyncio.to_thread` pattern)

### Expected Features

**Must have (v1.1 launch):**
- Persistent negotiation state in SQLite (the entire point of the milestone)
- State recovery on startup (load non-terminal negotiations from DB)
- `/health` liveness endpoint (Docker HEALTHCHECK depends on it)
- `/ready` readiness endpoint (checks audit DB writable, Gmail token present)
- Multi-stage Dockerfile with non-root user
- Docker Compose with named volume for `data/` persistence
- GitHub Actions CI (pytest + ruff + mypy on every push)
- GitHub Actions CD (build image, push to GHCR, SSH deploy on tag/manual trigger)
- Secret management pattern (env vars, never baked into image)
- Graceful shutdown (uvicorn signal handling for in-flight requests)

**Should have (add after first live deploy):**
- `@pytest.mark.live` integration tests with real credentials
- Retry decorator applied consistently to GmailClient and SheetsClient
- Startup validation checks (fail fast on bad credentials)
- Prometheus `/metrics` endpoint with custom business metrics
- Request ID middleware for log traceability

**Defer (v2+):**
- PostgreSQL migration (only if multi-host deployment is needed)
- Redis task queue (only if asyncio background tasks prove insufficient)
- Hosted log aggregation (only when cross-session log search is needed)
- OpenTelemetry traces (only when the system becomes multi-service)
- Circuit breaker for Anthropic API (existing tenacity + Slack alerting suffices)

### Architecture Approach

The architecture research confirms the existing FastAPI + services dict + SQLite pattern is sound and should not be redesigned. Production readiness is achieved by hardening what exists: adding a `negotiation_states` table to the existing SQLite audit DB, wrapping the in-memory dict with a persistence layer that writes on every state transition, adding health endpoints to the existing FastAPI app, and packaging the whole thing in a Docker container with a named volume for the `data/` directory. The `services` dict in `app.py` remains the central dependency container. Modified components are `initialize_services()`, `lifespan()`, and `create_app()` in `app.py`. New components are a health endpoints module, a state persistence layer, Dockerfile, docker-compose.yml, and GitHub Actions workflows.

**Major components (new or modified):**
1. **State persistence layer** -- SQLAlchemy async models + repository wrapping the existing `negotiation_states` dict with write-through to SQLite on every transition
2. **Health endpoints module** -- `/health` (liveness, always 200 if alive) and `/ready` (readiness, checks DB writable + Gmail token present)
3. **Dockerfile + docker-compose.yml** -- Multi-stage build, named volume for `data/`, HEALTHCHECK directive, non-root user
4. **GitHub Actions CI/CD** -- Lint/typecheck/test on push; build/push/deploy on tag or manual trigger
5. **Prometheus instrumentation** -- `Instrumentator().instrument(app).expose(app)` in `create_app()`
6. **Sentry integration** -- `sentry_sdk.init()` before app creation + `SentryProcessor` in structlog chain

### Critical Pitfalls

1. **OAuth2 `token.json` lost on container restart** -- Gmail and Sheets credential files must be on a Docker named volume or injected as environment variables. A container that starts without these files silently disables GmailClient and SheetsClient. Prevention: mount credentials from volume, validate at startup, fail fast if missing.

2. **`negotiation_states` dict wiped on any restart** -- The highest-impact pitfall. Active negotiations are silently dropped; influencers who reply after a restart get no response. Prevention: persist to SQLite on every state transition (not just shutdown), load non-terminal negotiations on startup, test by killing the container mid-negotiation and verifying recovery.

3. **Gmail Pub/Sub watch expires after container restarts** -- The 7-day watch expiration and the 6-day renewal timer become misaligned after restarts. Prevention: persist the watch expiration timestamp, schedule renewal relative to the actual expiration, not process uptime.

4. **SQLite WAL mode data loss on networked filesystems** -- WAL creates three files; network filesystems break file locking. Prevention: use local block storage for the Docker volume, validate WAL mode at startup, back up all three files.

5. **Slack Bolt Socket Mode deadlock or process death** -- The synchronous Bolt handler in `asyncio.to_thread` can deadlock on slash commands or crash the entire container on WebSocket disconnect. Prevention: add reconnection logic, monitor for crashes, plan eventual migration to async Bolt.

## Researcher Disagreement: SQLite vs. Redis for State Persistence

The STACK and FEATURES researchers recommend **SQLite-only** for persistent state (extending the existing audit DB with a new table via SQLAlchemy async). The ARCHITECTURE researcher recommends **Redis** for negotiation state, thread state, and Gmail history_id, adding a Redis container to docker-compose.yml.

**Resolution: SQLite wins for v1.1.** The rationale:
- SQLite is already in production for the audit trail, working with WAL mode. Adding a table is zero new infrastructure.
- Redis adds a second container, AOF persistence configuration, connection management, and a new failure mode (Redis down = all state reads fail).
- The agent runs on a single VM with a single asyncio event loop. There is no multi-instance coordination that would justify Redis.
- The ARCHITECTURE researcher's Redis recommendation appears oriented toward a future multi-VM deployment that is explicitly out of scope for v1.1.
- If multi-host deployment becomes necessary in the future, migrating from SQLite to PostgreSQL (or adding Redis) is a natural evolution -- but it should not be premature.

The ARCHITECTURE researcher's component design (health endpoints, Prometheus instrumentation, Docker layout, CI/CD workflow, request ID middleware) is adopted. Only the Redis-specific components are replaced with SQLite equivalents.

## Implications for Roadmap

Based on combined research, the v1.1 milestone naturally decomposes into 5 phases ordered by dependency.

### Phase 1: Settings and Health Infrastructure

**Rationale:** Health endpoints are a prerequisite for Docker HEALTHCHECK, and pydantic-settings is needed to cleanly manage environment variables across dev/CI/production. These are low-risk, low-complexity changes that establish the foundation for everything else.

**Delivers:** `pydantic-settings` BaseSettings class replacing `os.environ.get()` calls, `/health` liveness endpoint, `/ready` readiness endpoint (checks audit DB writable, Gmail token present), `.env.example` template.

**Features addressed:** `/health` liveness endpoint, `/ready` readiness endpoint, secret management pattern, startup validation checks.

**Avoids:** Pitfall: health check that always returns 200 (readiness endpoint checks real dependencies). Pitfall: confusing mid-runtime credential failures (startup validation).

### Phase 2: Persistent Negotiation State

**Rationale:** This is the highest-risk and highest-value item. Everything else (Docker, CI/CD) is standard plumbing; this is the one item that requires careful design of the serialization layer. It must be built and tested before the Dockerfile is finalized, because the Docker deployment depends on state surviving container restarts.

**Delivers:** SQLAlchemy async models for `negotiation_states` table in existing audit DB, Alembic migration, write-through persistence on every state transition, startup recovery (load non-terminal negotiations), `NegotiationStateMachine` serialization (state string + history list, not pickle).

**Features addressed:** Persistent negotiation state in SQLite, state recovery on startup.

**Uses:** SQLAlchemy 2.0.46 async + aiosqlite 0.22.1 + Alembic 1.18.4.

**Avoids:** Pitfall: `negotiation_states` dict lost on restart. Pitfall: pickle serialization (use JSON). Pitfall: relying on shutdown hooks (write on every transition, not on shutdown).

### Phase 3: Docker Packaging and Deployment

**Rationale:** With health endpoints and persistent state in place, the app is ready to be containerized. The Dockerfile depends on health endpoints for HEALTHCHECK and on state persistence for the named volume strategy to be meaningful.

**Delivers:** Multi-stage Dockerfile (uv-based build, non-root user, HEALTHCHECK), docker-compose.yml (app service + named volume for `data/`), `.dockerignore`, credential file mounting strategy (OAuth token + Sheets service account on named volume).

**Features addressed:** Multi-stage Dockerfile, Docker Compose file, graceful shutdown, Docker volume for SQLite persistence.

**Avoids:** Pitfall: OAuth2 `token.json` baked into image or lost on restart (volume mount). Pitfall: Sheets service account permission errors with non-root user (validate at startup). Pitfall: SQLite WAL on networked filesystem (verify local block storage).

### Phase 4: CI/CD Pipeline

**Rationale:** CI must be established and validated before CD is wired. The Docker image must build and pass all tests before automated deployment is possible. This phase depends on the Dockerfile from Phase 3.

**Delivers:** GitHub Actions CI workflow (lint with ruff, typecheck with mypy, test with pytest on every push), GitHub Actions CD workflow (build Docker image, push to GHCR, SSH deploy to VM on tag/manual trigger), test isolation (AUDIT_DB_PATH set to temp directory in CI).

**Features addressed:** GitHub Actions CI, GitHub Actions CD.

**Uses:** astral-sh/setup-uv v6, docker/build-push-action v6, appleboy/ssh-action.

**Avoids:** Pitfall: CI tests hitting real SQLite files or leaking state (temp path per test). Pitfall: auto-deploy on every commit (manual trigger or tag-based deploy).

### Phase 5: Monitoring, Observability, and Live Verification

**Rationale:** With the agent deployed and running, add the observability layer. This phase is intentionally last because monitoring is only useful once the system is live. It includes Prometheus metrics, Sentry error tracking, and the `@pytest.mark.live` integration test pattern.

**Delivers:** Prometheus `/metrics` endpoint via prometheus-fastapi-instrumentator, Sentry SDK integration with structlog bridge, request ID middleware for log traceability, `@pytest.mark.live` integration test marker and conftest pattern, post-deploy smoke test suite, Gmail watch expiration persistence and renewal fix.

**Features addressed:** Prometheus metrics, Sentry error tracking, live integration tests, Gmail watch auto-renewal fix.

**Uses:** prometheus-fastapi-instrumentator 7.1.0, prometheus-client 0.24.1, sentry-sdk 2.53.0, structlog-sentry 2.2.1, pytest-asyncio 1.3.0, pytest-httpx 0.36.0.

**Avoids:** Pitfall: Gmail watch expiry after restarts (persist expiration timestamp). Pitfall: Anthropic 529 vs 429 retry (enhance retry logic). Pitfall: Slack Bolt deadlock (add monitoring for WebSocket disconnects).

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Settings management and health endpoints are low-risk and create the foundation that state persistence and Docker both depend on.
- **Phase 2 before Phase 3:** State persistence must work before Docker packaging, because the entire point of Docker deployment is surviving restarts. If state persistence has bugs, they must be caught before the Dockerfile is finalized.
- **Phase 3 before Phase 4:** CI/CD depends on a working Dockerfile. The Docker image must build and the health check must pass before automated deployment is wired.
- **Phase 4 before Phase 5:** Monitoring is only useful after the system is deployed. Live verification tests need a running deployment target.
- **Within each phase:** Features are ordered by dependency (e.g., health endpoints before Docker HEALTHCHECK, CI before CD, Prometheus before custom business metrics).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Persistent State):** The serialization design for `NegotiationStateMachine` and `CampaignCPMTracker` objects requires inspecting the actual class fields. Alembic with SQLite requires `batch_alter_table` for all migrations -- verify this pattern works with the async engine. The startup recovery logic (loading non-terminal negotiations into the dict) needs careful testing for edge cases (corrupted JSON, schema changes between versions).
- **Phase 3 (Docker Packaging):** OAuth credential mounting strategy needs validation on the actual target VM. The interaction between non-root container user and file permissions for credential files is a known failure point. Test on the real deployment target, not just Docker Desktop.

Phases with standard patterns (skip deep research):
- **Phase 1 (Settings and Health):** pydantic-settings and health endpoints are thoroughly documented, trivial patterns.
- **Phase 4 (CI/CD):** GitHub Actions + GHCR + SSH deploy is a well-trodden path with official action documentation.
- **Phase 5 (Monitoring):** prometheus-fastapi-instrumentator and Sentry SDK integration are two-line additions with extensive documentation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified against PyPI on 2026-02-19. Compatibility matrix confirmed. No version uncertainty. |
| Features | HIGH | Feature landscape is straightforward production hardening. All features have clear implementation patterns and well-defined scope. |
| Architecture | HIGH (with caveat) | Patterns are well-established. The Redis vs. SQLite disagreement is resolved in favor of SQLite. The caveat is that the `NegotiationStateMachine` serialization design needs validation against the actual class during implementation. |
| Pitfalls | HIGH | All pitfalls are grounded in direct code observation of `src/negotiation/`. Prevention strategies are specific and actionable. The OAuth and WAL mode pitfalls are documented SQLite/Docker limitations. |

**Overall confidence:** HIGH

This is a well-researched production hardening milestone for a working application. The technology choices are conservative (SQLite, not PostgreSQL; Docker Compose, not Kubernetes; Prometheus metrics, not OpenTelemetry), the patterns are well-established, and the pitfalls are well-documented with clear prevention strategies. The only area requiring careful implementation attention is the state persistence migration (Phase 2), which involves serialization design that depends on the actual class internals.

### Gaps to Address

- **NegotiationStateMachine serialization:** The exact fields of `NegotiationStateMachine` and `CampaignCPMTracker` need to be inspected during Phase 2 planning. The research assumes they are simple (state string + history list + scalar fields), but the actual classes may have additional state that needs persisting.
- **Target VM filesystem type:** The SQLite WAL pitfall depends on whether the deployment VM uses local block storage or networked storage. This must be confirmed before Phase 3 implementation.
- **Gmail Pub/Sub endpoint reachability:** The deployed VM must be reachable from Google's Pub/Sub servers. If the VM is behind NAT, a reverse proxy (Cloudflare Tunnel, nginx) is needed. This is not covered in the research and must be confirmed during Phase 3.
- **Slack Bolt async migration timeline:** The Slack Bolt Socket Mode deadlock risk is documented but the prevention strategy for v1.1 is "monitor and add reconnection logic," not a full async migration. If the deadlock proves to be a frequent issue in production, an emergency migration to `AsyncSocketModeHandler` may be needed. The scope of that migration is not estimated.
- **pytest-asyncio 1.3.0 breaking changes:** The upgrade from 0.21.0 to 1.3.0 is a breaking change that requires `asyncio_mode = "auto"` in config and may require updating existing test fixtures. The scope of test updates is not estimated.

## Sources

### Primary (HIGH confidence)
- SQLAlchemy 2.0 async documentation (AsyncAdaptedQueuePool for file SQLite)
- PyPI version verification for all packages (2026-02-19)
- SQLite WAL mode documentation (sqlite.org/wal.html)
- Redis persistence documentation (AOF mode)
- FastAPI official Docker deployment guide
- GitHub Actions official documentation (setup-uv, docker/build-push-action, docker/login-action)
- Anthropic API error codes documentation
- Slack Bolt GitHub issues (#445, #994) for Socket Mode threading issues
- Google OAuth2 documentation (token invalidation, consent screen modes)
- Direct codebase analysis: `src/negotiation/app.py`, `resilience/retry.py`, `audit/store.py`, `auth/credentials.py`, `slack/takeover.py`

### Secondary (MEDIUM confidence)
- Docker multi-stage builds with uv (multiple 2025 blog posts, consistent patterns)
- FastAPI health check patterns (2025 community guides)
- prometheus-fastapi-instrumentator integration pattern (GitHub README)
- structlog-sentry bridge configuration (kiwicom/structlog-sentry GitHub)
- pytest marker skip pattern for live integration tests (pytest official docs)

### Tertiary (LOW confidence)
- Exact Grafana Cloud free tier capabilities for Prometheus remote write (may have changed)
- `appleboy/ssh-action` version stability (community action, not officially maintained by GitHub)
- Sentry free tier limits for the agent's expected event volume

---
*Research completed: 2026-02-19*
*Ready for roadmap: yes*
