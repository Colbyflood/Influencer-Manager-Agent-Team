# Roadmap: Influencer Negotiation Agent

## Milestones

- v1.0 MVP -- Phases 1-7 (shipped 2026-02-19)
- **v1.1 Production Readiness** -- Phases 8-12 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-7) -- SHIPPED 2026-02-19</summary>

- [x] Phase 1: Core Domain and Pricing Engine (3/3 plans) -- completed 2026-02-19
- [x] Phase 2: Email and Data Integration (3/3 plans) -- completed 2026-02-19
- [x] Phase 3: LLM Negotiation Pipeline (4/4 plans) -- completed 2026-02-19
- [x] Phase 4: Slack and Human-in-the-Loop (4/4 plans) -- completed 2026-02-19
- [x] Phase 5: Campaign Ingestion and Operational Readiness (4/4 plans) -- completed 2026-02-19
- [x] Phase 6: Runtime Orchestration Wiring (3/3 plans) -- completed 2026-02-19
- [x] Phase 7: Integration Hardening (2/2 plans) -- completed 2026-02-19

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### v1.1 Production Readiness (In Progress)

**Milestone Goal:** Make the v1.0 negotiation agent production-grade -- persistent state, deployment infrastructure, CI/CD, monitoring, and live verification with real services.

- [x] **Phase 8: Settings and Health Infrastructure** - Typed configuration, health endpoints, and startup credential validation
- [x] **Phase 9: Persistent Negotiation State** - SQLite-backed state persistence with crash recovery
- [x] **Phase 10: Docker Packaging and Deployment** - Multi-stage container with volume persistence (completed 2026-02-19)
- [x] **Phase 11: CI/CD Pipeline** - GitHub Actions automated lint, typecheck, and test on every push (completed 2026-02-19)
- [x] **Phase 12: Monitoring, Observability, and Live Verification** - Prometheus metrics, Sentry errors, request tracing, live tests, and Gmail watch renewal (completed 2026-02-19)

## Phase Details

### Phase 8: Settings and Health Infrastructure
**Goal**: Agent configuration is typed and validated, health status is externally observable, and bad credentials are caught at startup before any work begins
**Depends on**: Phase 7 (v1.0 complete)
**Requirements**: CONFIG-01, OBS-01, OBS-02, STATE-03
**Success Criteria** (what must be TRUE):
  1. Agent loads all configuration from environment variables and .env files without any raw os.environ calls in application code
  2. Hitting GET /health returns 200 when the agent process is running
  3. Hitting GET /ready returns 200 only when the audit database is writable and a valid Gmail token is present; returns 503 otherwise
  4. Agent refuses to start and prints a clear error message when Gmail token, Sheets service account, or Slack token is missing or invalid
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md — Centralized Settings class (pydantic-settings) and startup credential validation
- [x] 08-02-PLAN.md — Health/readiness endpoints and tests

### Phase 9: Persistent Negotiation State
**Goal**: Active negotiations survive process restarts and container redeployments -- no deals are silently lost
**Depends on**: Phase 8
**Requirements**: STATE-01, STATE-02
**Success Criteria** (what must be TRUE):
  1. Every negotiation state transition is written to SQLite before the response is returned, so killing the process at any point loses zero state
  2. After a restart, all non-terminal negotiations are loaded from the database and the agent resumes responding to influencer emails on those threads
  3. The in-memory negotiation_states dict and the SQLite table are always consistent -- no drift between them during normal operation
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md — State persistence module (schema, store, serializers) and domain object serialization methods
- [x] 09-02-PLAN.md — Wire state store into app.py (initialization, startup recovery, write-on-every-transition)

### Phase 10: Docker Packaging and Deployment
**Goal**: Agent runs as a Docker container that persists data across restarts and can be deployed to any VM with docker compose up
**Depends on**: Phase 9
**Requirements**: DEPLOY-01, DEPLOY-02
**Success Criteria** (what must be TRUE):
  1. Running docker compose up starts the agent, and GET /health returns 200 within 30 seconds
  2. The Docker container runs as a non-root user and uses a multi-stage build (build stage separate from runtime stage)
  3. SQLite database and credential files persist across docker compose down and docker compose up cycles via a named volume
  4. Docker HEALTHCHECK directive automatically restarts the container if the health endpoint stops responding
**Plans**: 2 plans

Plans:
- [ ] 10-01-PLAN.md — Multi-stage Dockerfile, .dockerignore, and entrypoint.sh (non-root user, HEALTHCHECK)
- [ ] 10-02-PLAN.md — docker-compose.yml with named volume and end-to-end verification

### Phase 11: CI/CD Pipeline
**Goal**: Every push to GitHub is automatically linted, typechecked, and tested so regressions are caught before merge
**Depends on**: Phase 10
**Requirements**: DEPLOY-03
**Success Criteria** (what must be TRUE):
  1. Pushing a commit to any branch triggers a GitHub Actions workflow that runs ruff lint, mypy typecheck, and pytest
  2. A pull request cannot be merged if the CI workflow fails (status check visible on PR)
  3. CI tests run in isolation without touching real databases or external services
**Plans**: 1 plan

Plans:
- [x] 11-01-PLAN.md — GitHub Actions CI workflow (ruff, mypy, pytest) and branch protection

### Phase 12: Monitoring, Observability, and Live Verification
**Goal**: Agent errors are tracked, performance is measurable, requests are traceable end-to-end, and real service connections are verified by automated tests
**Depends on**: Phase 11
**Requirements**: OBS-03, OBS-04, OBS-05, CONFIG-02, CONFIG-03
**Success Criteria** (what must be TRUE):
  1. GET /metrics returns Prometheus-format metrics including HTTP request counts/latencies and custom business metrics (active negotiations, deals closed)
  2. Unhandled exceptions are reported to Sentry with full request context and structlog fields attached
  3. Every inbound HTTP request gets a unique request ID that appears in all log entries for that request
  4. Running pytest -m live with real credentials verifies actual Gmail send/receive, Sheets read, and Slack message delivery
  5. Gmail Pub/Sub watch is renewed based on its persisted expiration timestamp, not process uptime, so restarts do not cause missed emails

**Plans**: 3 plans

Plans:
- [x] 12-01-PLAN.md — Prometheus metrics, Sentry error reporting, and request ID tracing middleware
- [x] 12-02-PLAN.md — Opt-in @pytest.mark.live integration tests for Gmail, Sheets, and Slack
- [ ] 12-03-PLAN.md — Gmail watch expiration persistence and expiry-aware renewal

## Progress

**Execution Order:**
Phases execute in numeric order: 8 -> 9 -> 10 -> 11 -> 12

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Domain and Pricing Engine | v1.0 | 3/3 | Complete | 2026-02-19 |
| 2. Email and Data Integration | v1.0 | 3/3 | Complete | 2026-02-19 |
| 3. LLM Negotiation Pipeline | v1.0 | 4/4 | Complete | 2026-02-19 |
| 4. Slack and Human-in-the-Loop | v1.0 | 4/4 | Complete | 2026-02-19 |
| 5. Campaign Ingestion and Operational Readiness | v1.0 | 4/4 | Complete | 2026-02-19 |
| 6. Runtime Orchestration Wiring | v1.0 | 3/3 | Complete | 2026-02-19 |
| 7. Integration Hardening | v1.0 | 2/2 | Complete | 2026-02-19 |
| 8. Settings and Health Infrastructure | v1.1 | Complete    | 2026-02-19 | 2026-02-19 |
| 9. Persistent Negotiation State | v1.1 | Complete    | 2026-02-19 | 2026-02-19 |
| 10. Docker Packaging and Deployment | 2/2 | Complete    | 2026-02-19 | - |
| 11. CI/CD Pipeline | 1/1 | Complete    | 2026-02-19 | - |
| 12. Monitoring, Observability, and Live Verification | 3/3 | Complete   | 2026-02-19 | - |
