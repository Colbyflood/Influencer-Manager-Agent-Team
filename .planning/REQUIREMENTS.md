# Requirements: Influencer Negotiation Agent

**Defined:** 2026-02-19
**Core Value:** The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome -- every agreed deal must result in a clear, actionable Slack notification to the team.

## v1.1 Requirements

Requirements for production readiness. Each maps to roadmap phases.

### State Persistence

- [ ] **STATE-01**: Agent persists negotiation state to SQLite on every state transition so no deals are lost on restart
- [ ] **STATE-02**: Agent recovers non-terminal negotiations from database on startup so in-progress deals resume automatically
- [x] **STATE-03**: Agent validates credentials (Gmail token, Sheets SA, Slack token) at startup and fails fast with clear errors

### Health & Observability

- [x] **OBS-01**: Agent exposes /health liveness endpoint that returns 200 when the process is alive
- [x] **OBS-02**: Agent exposes /ready readiness endpoint that checks DB writable and Gmail token present
- [ ] **OBS-03**: Agent exposes /metrics Prometheus endpoint with HTTP request metrics and custom business metrics (active negotiations, deals closed)
- [ ] **OBS-04**: Agent reports errors to Sentry with full request context via structlog bridge
- [ ] **OBS-05**: Agent attaches a unique request ID to every inbound request for end-to-end log traceability

### Deployment

- [ ] **DEPLOY-01**: Agent runs in a multi-stage Docker container with non-root user and HEALTHCHECK directive
- [ ] **DEPLOY-02**: Agent persists SQLite database and credential files via Docker named volume
- [ ] **DEPLOY-03**: GitHub Actions CI runs ruff lint, mypy typecheck, and pytest on every push

### Configuration & Testing

- [x] **CONFIG-01**: Agent loads all configuration from environment variables via pydantic-settings with .env file support
- [ ] **CONFIG-02**: Agent includes @pytest.mark.live integration tests that verify real Gmail, Sheets, and Slack connections
- [ ] **CONFIG-03**: Agent persists Gmail watch expiration timestamp and renews relative to actual expiry, not process uptime

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Deployment

- **DEPLOY-04**: GitHub Actions CD builds Docker image, pushes to GHCR, and SSH deploys to VM on tag/manual trigger
- **DEPLOY-05**: Agent handles graceful shutdown with proper uvicorn signal handling for in-flight requests

### Observability

- **OBS-06**: Agent implements circuit breaker for Anthropic API with Slack alerting on sustained failures
- **OBS-07**: Agent sends logs to hosted aggregation service for cross-session search

## Out of Scope

| Feature | Reason |
|---------|--------|
| PostgreSQL migration | Over-engineered for single-VM scale; SQLite sufficient |
| Redis state cache | Adds second container and failure mode for no benefit at current scale |
| Kubernetes/ECS | Massive operational overhead for single-VM target |
| OpenTelemetry traces | Requires collector sidecar; Prometheus + Sentry covers the need |
| gunicorn process manager | Forking model breaks Slack Bolt Socket Mode asyncio.to_thread pattern |
| Multi-host deployment | Single VM is the target for v1.1; scale later if needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONFIG-01 | Phase 8 | Complete |
| OBS-01 | Phase 8 | Complete |
| OBS-02 | Phase 8 | Complete |
| STATE-03 | Phase 8 | Complete |
| STATE-01 | Phase 9 | Pending |
| STATE-02 | Phase 9 | Pending |
| DEPLOY-01 | Phase 10 | Pending |
| DEPLOY-02 | Phase 10 | Pending |
| DEPLOY-03 | Phase 11 | Pending |
| OBS-03 | Phase 12 | Pending |
| OBS-04 | Phase 12 | Pending |
| OBS-05 | Phase 12 | Pending |
| CONFIG-02 | Phase 12 | Pending |
| CONFIG-03 | Phase 12 | Pending |

**Coverage:**
- v1.1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after roadmap creation*
