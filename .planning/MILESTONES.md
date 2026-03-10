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


## v1.2 Real-World Negotiation Intelligence (Shipped: 2026-03-08)

**Phases completed:** 5 phases, 13 plans
**Tests:** 832+ passing | **Total LOC:** ~23,872 Python
**Timeline:** 1 day (2026-03-08) | **Requirements:** 26/26 satisfied

**Key accomplishments:**
- Expanded campaign data model from 8 to 42 ClickUp form fields with 11 Pydantic sub-models (goals, deliverable scenarios, usage rights, budget constraints, product leverage, requirements)
- Per-campaign CPM Target + Leniency replaces hardcoded $20-$30 range with dynamic pricing boundaries
- AGM negotiation playbook with 9 categorized email examples and stage-aware example selection via YAML frontmatter
- Full negotiation lever stack: 8-step deterministic priority chain (cost bounds > deliverable tiers > usage rights > product > syndication > CPM sharing > graceful exit)
- Counterparty intelligence: signal-based classifier detects influencer vs talent manager/agency, per-thread contact tracking, tone adaptation (transactional vs relationship-driven)
- AGM-style email composition with SOW formatter (strikethrough rate adjustments), agreement confirmation emails with payment terms and next steps

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md)

**Known tech debt (v1.2 acknowledged):**
- `mailparser_reply` dependency missing from environment (pre-existing, causes import errors in orchestration/email tests)
- LLM output quality for tone adaptation and AGM style not yet validated with real email threads
- Contact tracker is in-memory (not persisted to SQLite like negotiation state)

---


## v1.3 Campaign Dashboard (Shipped: 2026-03-09)

**Phases completed:** 4 phases, 8 plans
**Tests:** 857 passing | **Total LOC:** ~11,372 Python + 856 TypeScript
**Timeline:** 1 day (2026-03-08 to 2026-03-09) | **Commits:** 30
**Requirements:** 14/14 satisfied

**Key accomplishments:**
- React 19 + Vite + TypeScript + Tailwind CSS 4 frontend served alongside FastAPI backend at /dashboard with multi-stage Docker build
- Campaign overview dashboard with auto-polling (30s configurable), status aggregation (active/agreed/escalated/total), and campaign-level metrics (avg CPM, % closed, budget utilization)
- Per-influencer negotiation detail view with color-coded state badges, drill-down from campaign list, and clickable rows leading to individual timelines
- Per-influencer negotiation timeline showing state transitions from state machine history and email activity from SQLite audit trail with expandable email bodies
- Dashboard-driven negotiation controls: Pause/Resume/Stop buttons per influencer with state-aware rendering, backend state machine extensions (PAUSED/STOPPED states), and email processing guard
- Bulk stop-by-agency API endpoint for stopping all negotiations associated with a talent agent/agency in one request

**Archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

**Known tech debt (v1.3 acknowledged):**
- Vite `base` not set to `/dashboard/` — production static asset URLs may need adjustment
- `rejected` count not displayed on CampaignCard (data available in API, omitted from UI)
- `stop-by-agency` bulk endpoint has no frontend UI trigger (API-only)
- Contact tracker is in-memory (pre-existing from v1.2)

---


## v1.4 Per-Campaign Influencer Sheets (Shipped: 2026-03-10)

**Phases completed:** 2 phases, 4 plans, 8 tasks
**Files modified:** 25 (2,363 insertions, 21 deletions)
**Timeline:** 1 day (2026-03-09) | **Commits:** 20
**Requirements:** 10/10 satisfied

**Key accomplishments:**
- Per-campaign sheet routing via Campaign model fields (`influencer_sheet_tab`, `influencer_sheet_id`) parsed from ClickUp forms
- SheetsClient extended with `spreadsheet_key_override` for reading from alternate spreadsheets per campaign
- Ingestion pipeline wired to route `find_influencer()` calls to per-campaign sheet tabs with fallback to master "Sheet1"
- SQLite-backed SheetMonitor with SHA-256 row hashing for new/modified influencer detection and dedup tracking
- Async hourly polling loop that auto-starts negotiations for newly discovered influencers and sends Slack alerts for modified rows

**Archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

**Known tech debt (v1.4 acknowledged):**
- `init_processed_influencers_table` called in both `monitor.py` and `app.py` (redundant but harmless)
- Sheet monitor requires live Google Sheets + Slack for full integration testing (no automated integration test)

---

