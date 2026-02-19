# Milestones

## v1.0 MVP (Shipped: 2026-02-19)

**Phases completed:** 7 phases, 23 plans
**Tests:** 691 passing | **Source LOC:** 6,799 Python | **Test LOC:** 9,595 Python
**Timeline:** 2 days (2026-02-18 to 2026-02-19) | **Commits:** 108
**Requirements:** 22/22 satisfied

**Key accomplishments:**
- Deterministic CPM-based pricing engine ($20-$30 range) with platform-specific rate cards and negotiation state machine
- Gmail API integration with send/receive, Pub/Sub push notifications, MIME parsing, and thread continuity
- LLM-powered negotiation pipeline with intent classification, counter-offer composition, knowledge base guidance, and deterministic validation gate
- Slack human-in-the-loop with configurable escalation triggers, agreement alerts, and human takeover detection
- Campaign ingestion from ClickUp webhooks with CampaignCPMTracker and SQLite audit trail (CLI + Slack query)
- End-to-end runtime wiring connecting all components in FastAPI with lifespan management
- Integration hardening: graceful degradation, engagement-rate pricing, inbound email audit logging

**Archive:** [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) | [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) | [v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md)

**Known tech debt (v1 acknowledged):**
- In-memory negotiation_states dict lost on process restart
- RateCard/calculate_deliverable_rate not wired into live pipeline
- 3 human verification items pending (live startup, ClickUp E2E, CLI audit output)

---


## v1.1 Production Readiness (Shipped: 2026-02-19)

**Phases completed:** 5 phases, 10 plans
**Tests:** 731 passing (+ 4 live) | **Total LOC:** ~21,721 Python
**Timeline:** 1 day (2026-02-19) | **Commits:** 53
**Requirements:** 14/14 satisfied

**Key accomplishments:**
- Centralized pydantic-settings configuration with startup credential validation and health/readiness probes
- SQLite-backed negotiation state persistence with crash recovery -- no deals lost on restart
- Multi-stage Docker container with non-root execution, volume persistence, and HEALTHCHECK auto-restart
- GitHub Actions CI pipeline with lint, typecheck, and test jobs plus branch protection
- Prometheus metrics, Sentry error reporting, and request ID tracing for full observability
- Live integration tests for Gmail, Sheets, and Slack with expiration-aware Gmail watch renewal

**Archive:** [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) | [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) | [v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

**Known tech debt (v1.1 acknowledged):**
- Docker build/compose not tested in CI (Docker CLI unavailable in execution environment)
- Target VM filesystem type must be confirmed as local block storage before deployment
- Branch protection configured via GitHub UI (cannot verify programmatically)
- Live integration tests require real credentials (not run in CI)
- Sentry DSN not yet provisioned (code handles empty DSN as no-op)

---

