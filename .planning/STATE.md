# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome -- every agreed deal must result in a clear, actionable Slack notification to the team.
**Current focus:** Phase 12 - Monitoring, Observability, and Live Verification

## Current Position

Phase: 12 of 12 (Monitoring, Observability, and Live Verification)
Plan: 2 of 3 in current phase
Status: In Progress
Last activity: 2026-02-19 -- Completed 12-02 (Live integration tests for Gmail, Sheets, Slack)

Progress: [=============================.] 97% (32/33 plans across all milestones)

## Performance Metrics

**v1.0 Velocity (reference):**
- Total plans completed: 23
- Average duration: 4min
- Total execution time: 1.47 hours

**v1.1 By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 8 | 2/2 | 10min | 5min |
| Phase 9 | 2/2 | 8min | 4min |
| Phase 10 | 2/2 | 3min | 1.5min |
| Phase 11 | 1/1 | 20min | 20min |
| Phase 12 | 2/3 | 6min | 3min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.1 research]: SQLite over Redis for state persistence (zero new infrastructure)
- [v1.1 research]: Stay on single-VM Docker Compose (no Kubernetes)
- [v1.1 research]: Prometheus + Sentry for observability (no OpenTelemetry)
- [08-01]: Settings stored on services dict and FastAPI app.state for endpoint access
- [08-01]: Tests pass Settings objects directly instead of patching env vars
- [08-01]: Slack functions require explicit tokens (no env var fallback)
- [08-02]: Health routes on top-level app (not webhook sub-router) for clean URLs
- [08-02]: SELECT 1 for DB check (no INSERT/DELETE) per research guidance
- [08-02]: asyncio.to_thread for blocking SQLite in async readiness endpoint
- [09-01]: Decimal values serialized as strings in JSON for lossless round-trips
- [09-01]: INSERT OR REPLACE with COALESCE subquery to preserve original created_at
- [09-01]: load_active filters via TERMINAL_STATES from transitions module (single source of truth)
- [09-01]: from_snapshot pattern for explicit domain object reconstruction from persisted data
- [09-02]: serialize_context used inside store.save() for transparent Decimal handling
- [09-02]: Startup recovery populates negotiation_states before request processing
- [09-02]: State save guarded with if state_store is not None for backward compatibility
- [10-01]: setpriv over gosu for privilege drop (already in Debian slim, no extra install)
- [10-01]: HEALTHCHECK kills PID 1 on failure for auto-restart with docker-compose restart policy
- [10-01]: No USER directive in Dockerfile -- entrypoint runs as root to fix volumes, then drops privileges
- [10-02]: Single named volume agent_data for both SQLite DB and credentials (simpler backup and management)
- [10-02]: Explicit AUDIT_DB_PATH override even though default resolves correctly (clarity over implicit CWD dependency)
- [10-02]: SHEETS_SERVICE_ACCOUNT_PATH override required (default ~/.config path does not exist in container)
- [10-02]: No user: directive in compose -- entrypoint handles privilege drop after volume chown
- [11-01]: No hardcoded Python version in CI -- astral-sh/setup-uv reads .python-version automatically
- [11-01]: ruff format applied to entire codebase (30 files) to pass CI format check from day one
- [11-01]: Branch protection configured via GitHub Settings UI (most reliable for admin-level operations)
- [12-01]: SentryProcessor placed after add_log_level and before TimeStamper in structlog chain
- [12-01]: Business metrics updated at state transitions (not by DB polling) for real-time accuracy
- [12-01]: RequestIdMiddleware added before instrumentator so request_id is in all instrumented logs
- [12-02]: Native pytest marker via pyproject.toml addopts (no custom CLI options or collection hooks)
- [12-02]: Session-scoped live fixtures to avoid re-creating API clients per test
- [12-02]: Credential-skip pattern: each fixture pytest.skip() if creds unavailable

### Pending Todos

None.

### Blockers/Concerns

- ~~NegotiationStateMachine serialization design needs validation against actual class fields (Phase 9 risk)~~ RESOLVED in 09-01: from_snapshot classmethod validated and tested
- Target VM filesystem type must be confirmed as local block storage before Docker deployment (Phase 10 risk)

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 12-02-PLAN.md (Live integration tests for Gmail, Sheets, Slack)
Resume file: None
