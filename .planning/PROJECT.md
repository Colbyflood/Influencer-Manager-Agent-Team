# Influencer Negotiation Agent

## What This Is

An AI-powered agent that handles influencer rate negotiations via email on behalf of marketing teams. The agent picks up email threads where influencers have already responded to outreach, negotiates deliverable rates using CPM-based pricing logic ($20-$30 CPM range), and alerts the team via Slack when agreements are reached or escalation is needed. It operates in hybrid mode -- autonomously handling routine negotiation while escalating edge cases to humans. The system is production-ready with persistent state, Docker deployment, CI/CD, and full observability.

## Core Value

The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome -- every agreed deal must result in a clear, actionable Slack notification to the team.

## Current State

**Shipped:** v1.1 Production Readiness (2026-02-19)
**Codebase:** ~21,721 LOC Python (source + tests)
**Tests:** 731 passing + 4 live integration tests
**Tech stack:** Python 3.12+, FastAPI, Anthropic SDK, Gmail API, Google Sheets API, Slack Bolt, SQLite, Pydantic v2, Docker, GitHub Actions, Prometheus, Sentry, structlog

The system can:
1. Receive inbound emails via Gmail Pub/Sub and run the full negotiation pipeline
2. Ingest campaigns from ClickUp and start negotiations for found influencers
3. Classify intent and compose counter-offers using LLM with knowledge base guidance
4. Escalate edge cases to Slack with full context (configurable triggers)
5. Detect agreement and notify the team with actionable alerts
6. Support human takeover of any thread
7. Log all actions to a queryable SQLite audit trail (CLI + Slack)
8. Persist negotiation state to SQLite -- survives restarts with zero data loss
9. Deploy via `docker compose up` with health checks and auto-restart
10. Report metrics to Prometheus, errors to Sentry, with request ID tracing

## Requirements

### Validated

- ✓ EMAIL-01: Agent can send emails via Gmail API on behalf of the team -- v1.0
- ✓ EMAIL-02: Agent can receive and process inbound emails via Gmail API with push notifications -- v1.0
- ✓ EMAIL-03: Agent maintains email thread context so influencers see a coherent conversation history -- v1.0
- ✓ EMAIL-04: Agent can parse influencer reply content from email threads (MIME, inline, forwarding) -- v1.0
- ✓ NEG-01: Agent reads influencer data from Google Sheet and pulls proposed pay range based on CPM -- v1.0
- ✓ NEG-02: Agent uses pre-calculated pay range to guide negotiation ($20 floor to $30 ceiling CPM) -- v1.0
- ✓ NEG-03: Agent supports platform-specific deliverable pricing (Instagram, TikTok, YouTube) -- v1.0
- ✓ NEG-04: Agent tracks negotiation state across multi-turn conversations -- v1.0
- ✓ NEG-05: Agent extracts rate proposals and intent from free-text email replies using LLM -- v1.0
- ✓ NEG-06: Agent composes counter-offer emails with calculated rates and clear terms -- v1.0
- ✓ NEG-07: Agent enforces rate boundaries and escalates when demands exceed $30 CPM -- v1.0
- ✓ HUMAN-01: Agent escalates to Slack with full context -- v1.0
- ✓ HUMAN-02: Agent escalates based on configurable trigger rules -- v1.0
- ✓ HUMAN-03: Agent detects agreement and sends actionable Slack alert -- v1.0
- ✓ HUMAN-04: Agent supports human takeover of any thread -- v1.0
- ✓ DATA-01: Agent accepts campaign data from ClickUp form submissions -- v1.0
- ✓ DATA-02: Agent reads influencer outreach data from Google Sheet -- v1.0
- ✓ DATA-03: Agent logs every sent/received email with timestamps, state, and rates -- v1.0
- ✓ DATA-04: Agent maintains queryable audit trail by influencer, campaign, or date range -- v1.0
- ✓ KB-01: Agent references knowledge base of influencer marketing best practices -- v1.0
- ✓ KB-02: Agent references negotiation strategy guidelines when composing responses -- v1.0
- ✓ KB-03: Knowledge base files are editable without code changes -- v1.0
- ✓ CONFIG-01: Agent loads all configuration from environment variables via pydantic-settings with .env file support -- v1.1
- ✓ STATE-01: Agent persists negotiation state to SQLite on every state transition so no deals are lost on restart -- v1.1
- ✓ STATE-02: Agent recovers non-terminal negotiations from database on startup so in-progress deals resume automatically -- v1.1
- ✓ STATE-03: Agent validates credentials at startup and fails fast with clear errors -- v1.1
- ✓ OBS-01: Agent exposes /health liveness endpoint that returns 200 when the process is alive -- v1.1
- ✓ OBS-02: Agent exposes /ready readiness endpoint that checks DB writable and Gmail token present -- v1.1
- ✓ OBS-03: Agent exposes /metrics Prometheus endpoint with HTTP request metrics and custom business metrics -- v1.1
- ✓ OBS-04: Agent reports errors to Sentry with full request context via structlog bridge -- v1.1
- ✓ OBS-05: Agent attaches a unique request ID to every inbound request for end-to-end log traceability -- v1.1
- ✓ DEPLOY-01: Agent runs in a multi-stage Docker container with non-root user and HEALTHCHECK directive -- v1.1
- ✓ DEPLOY-02: Agent persists SQLite database and credential files via Docker named volume -- v1.1
- ✓ DEPLOY-03: GitHub Actions CI runs ruff lint, mypy typecheck, and pytest on every push -- v1.1
- ✓ CONFIG-02: Agent includes @pytest.mark.live integration tests that verify real Gmail, Sheets, and Slack connections -- v1.1
- ✓ CONFIG-03: Agent persists Gmail watch expiration timestamp and renews relative to actual expiry, not process uptime -- v1.1

### Active

(No active requirements -- define with `/gsd:new-milestone`)

### Out of Scope

- Full outreach automation (cold email) -- future agent handles this; team uses Instantly today
- Campaign-level CPM optimization across influencers -- future "strategist" agent territory
- Web dashboard -- v1 uses Slack notifications; dashboard deferred
- Contract generation/sending -- legal liability; human sends contracts after agent alerts deal
- Direct platform API integration for pulling influencer metrics -- metrics are pre-loaded
- Fully autonomous mode -- hybrid with human escalation; trust must be earned
- DM/chat negotiation -- email-first; platform DM APIs are restricted
- Multi-language support -- negotiation nuance doesn't translate well; English-only
- PostgreSQL migration -- over-engineered for single-VM scale; SQLite sufficient
- Redis state cache -- adds second container and failure mode for no benefit at current scale
- Kubernetes/ECS -- massive operational overhead for single-VM target
- OpenTelemetry traces -- requires collector sidecar; Prometheus + Sentry covers the need

## Context

- Team currently uses Instantly for cold email outreach, then manually handles negotiation replies
- Influencer metrics (avg views from 9 recent posts) are pre-loaded into campaign data, not pulled live
- Campaign information is input via ClickUp forms with key details per client project
- CPM pricing model: start negotiations at $20 CPM, willing to move up toward $30 CPM per influencer
- $30 CPM is the per-influencer escalation threshold; future agent will manage campaign-level CPM averaging
- This is the first agent in a planned team of collaborative agents covering the full influencer marketing pipeline
- v1.0 shipped with 691 tests, 22/22 requirements satisfied, all E2E flows verified
- v1.1 added 40 more tests (731 total + 4 live), 14/14 production requirements satisfied
- Deployment target is a single VM with Docker Compose

## Constraints

- **Email integration**: Gmail API with Pub/Sub push notifications for reliable send/receive with threading
- **Slack integration**: Slack Bolt with Block Kit formatting for actionable alerts
- **Data input**: ClickUp webhook endpoint for structured campaign data ingestion
- **Negotiation logic**: CPM calculation excludes viral outlier posts; deterministic pricing engine (no LLM in pricing)
- **Hybrid mode**: Every email the agent sends is reviewable; escalation includes full context
- **Audit trail**: SQLite-backed, queryable via CLI and Slack /audit command
- **Deployment**: Single-VM Docker Compose with named volumes for persistence
- **CI/CD**: GitHub Actions with ruff, mypy, pytest; branch protection on main

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid mode for v1 | Build trust before full autonomy; reduce risk of bad negotiations | ✓ Good -- escalation system works well |
| Slack for escalation + alerts (no dashboard) | Keep v1 simple; dashboard is future scope | ✓ Good -- Block Kit alerts are actionable |
| Pre-loaded metrics (no live API pulls) | Simpler architecture; metrics already available from existing workflow | ✓ Good -- decouples from external APIs |
| Gmail API for email | Reliable send/receive with threading and Pub/Sub push notifications | ✓ Good -- MIME parsing handles edge cases |
| CPM-based pricing ($20-$30 range) | Matches team's existing negotiation strategy | ✓ Good -- deterministic engine is predictable |
| Anthropic SDK for LLM | Intent classification + email composition; structured outputs for reliability | ✓ Good -- validation gate catches LLM errors |
| SQLite for audit trail and state | Simple, zero-config, sufficient for single-VM query patterns | ✓ Good -- extended to negotiation state in v1.1 |
| Knowledge base as flat files | Team can edit without code changes (KB-03 requirement) | ✓ Good -- stored at project root |
| Deterministic validation gate | No LLM validates LLM output; regex + string matching only | ✓ Good -- catches dollar amount errors reliably |
| SQLite over Redis for state persistence | Zero new infrastructure; single-file backup; sufficient for single-VM | ✓ Good -- crash recovery verified |
| Single-VM Docker Compose (no Kubernetes) | Avoids massive operational overhead for current scale | ✓ Good -- `docker compose up` is the entire deploy |
| Prometheus + Sentry (no OpenTelemetry) | Avoids collector sidecar; covers metrics + errors + tracing needs | ✓ Good -- /metrics, Sentry, request IDs all working |
| pydantic-settings for configuration | Type-safe, .env support, no raw os.environ calls | ✓ Good -- 16 config fields, all validated |
| setpriv for privilege drop in Docker | Already in Debian slim, no extra install (vs gosu) | ✓ Good -- simpler than USER directive |
| Native pytest markers for live tests | No custom CLI options; `addopts` excludes by default | ✓ Good -- `pytest -m live` overrides cleanly |
| Singleton row pattern for watch state | Simpler than key-value table for single Gmail watch | ✓ Good -- CHECK(id=1) constraint enforces it |

---
*Last updated: 2026-02-19 after v1.1 milestone completion*
