# Roadmap: Influencer Negotiation Agent

## Milestones

- ✅ **v1.0 MVP** - Phases 1-7 (shipped 2026-02-19)
- ✅ **v1.1 Production Readiness** - Phases 8-12 (shipped 2026-02-19)
- ✅ **v1.2 Real-World Negotiation Intelligence** - Phases 13-17 (shipped 2026-03-08)
- 🚧 **v1.3 Campaign Dashboard** - Phases 18-21 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

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

<details>
<summary>v1.1 Production Readiness (Phases 8-12) -- SHIPPED 2026-02-19</summary>

- [x] Phase 8: Settings and Health Infrastructure (2/2 plans) -- completed 2026-02-19
- [x] Phase 9: Persistent Negotiation State (2/2 plans) -- completed 2026-02-19
- [x] Phase 10: Docker Packaging and Deployment (2/2 plans) -- completed 2026-02-19
- [x] Phase 11: CI/CD Pipeline (1/1 plan) -- completed 2026-02-19
- [x] Phase 12: Monitoring, Observability, and Live Verification (3/3 plans) -- completed 2026-02-19

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>v1.2 Real-World Negotiation Intelligence (Phases 13-17) -- SHIPPED 2026-03-08</summary>

- [x] Phase 13: Campaign Data Model Expansion (3/3 plans) -- completed 2026-03-08
- [x] Phase 14: Knowledge Base Rewrite (2/2 plans) -- completed 2026-03-08
- [x] Phase 15: Negotiation Levers and Strategy (3/3 plans) -- completed 2026-03-08
- [x] Phase 16: Counterparty Intelligence (3/3 plans) -- completed 2026-03-08
- [x] Phase 17: Email Composition and Style (2/2 plans) -- completed 2026-03-08

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

### 🚧 v1.3 Campaign Dashboard (In Progress)

**Milestone Goal:** Give the team a real-time web dashboard to monitor all campaigns, see per-influencer negotiation progress, and control the agent without relying solely on Slack.

- [x] **Phase 18: Frontend Foundation** - React + Tailwind app scaffolding served alongside FastAPI backend (completed 2026-03-09)
- [x] **Phase 19: Campaign Overview** - Campaign list API and dashboard view with status aggregation and polling (completed 2026-03-09)
- [x] **Phase 20: Negotiation Detail** - Per-influencer negotiation data, state timeline, and campaign detail view (completed 2026-03-09)
- [ ] **Phase 21: Negotiation Controls** - Pause, resume, and stop negotiations from the dashboard

## Phase Details

### Phase 18: Frontend Foundation
**Goal**: Team has a working React + Tailwind frontend application served alongside the existing FastAPI backend
**Depends on**: Nothing (first phase of v1.3; builds on existing FastAPI from v1.1)
**Requirements**: UI-01, UI-02
**Success Criteria** (what must be TRUE):
  1. A React + Tailwind CSS application builds successfully and renders a page in the browser
  2. The frontend is served alongside the existing FastAPI backend (static files or dev proxy) without breaking any existing API endpoints
  3. Navigating to the dashboard URL returns the React application, not a 404
**Plans**: 2 plans

Plans:
- [ ] 18-01-PLAN.md -- Scaffold React + Vite + TypeScript + Tailwind CSS app in frontend/
- [ ] 18-02-PLAN.md -- Integrate frontend with FastAPI backend (static serving, Dockerfile)

### Phase 19: Campaign Overview
**Goal**: Team can see all campaigns at a glance with live status summaries and key metrics
**Depends on**: Phase 18
**Requirements**: API-01, VIEW-01, VIEW-04, UI-03
**Success Criteria** (what must be TRUE):
  1. User sees a list of all campaigns with per-campaign status counts (active negotiations, agreed, escalated, total influencers)
  2. User sees campaign-level metrics: average CPM achieved, percentage of negotiations closed, budget utilization
  3. Dashboard data refreshes automatically at a configurable polling interval without manual page reload
  4. Campaign list API endpoint returns correct status aggregation when queried directly
**Plans**: 2 plans

Plans:
- [ ] 19-01-PLAN.md -- Campaign list API endpoint with status aggregation and metrics
- [ ] 19-02-PLAN.md -- Frontend campaign cards with status counts, metrics, and auto-polling

### Phase 20: Negotiation Detail
**Goal**: Team can drill into any campaign and inspect per-influencer negotiation progress, state history, and rate evolution
**Depends on**: Phase 19
**Requirements**: API-02, API-04, VIEW-02, VIEW-03
**Success Criteria** (what must be TRUE):
  1. User can click a campaign and see every influencer with their current negotiation state, rate, round count, and counterparty type
  2. User can view a per-influencer timeline showing each state transition, emails exchanged, and how the rate changed over time
  3. Campaign detail API endpoint returns per-influencer negotiation data with all required fields
  4. Timeline API endpoint returns chronological state transitions and email history for a given influencer negotiation
**Plans**: 2 plans

Plans:
- [ ] 20-01-PLAN.md -- Campaign detail and timeline API endpoints (backend)
- [ ] 20-02-PLAN.md -- Campaign detail view and negotiation timeline UI (frontend)

### Phase 21: Negotiation Controls
**Goal**: Team can control the agent directly from the dashboard -- pausing, resuming, or stopping negotiations without relying on Slack
**Depends on**: Phase 20
**Requirements**: API-03, CTRL-01, CTRL-02, CTRL-03
**Success Criteria** (what must be TRUE):
  1. User can pause or stop an active negotiation with a specific influencer from the dashboard, and the agent stops sending emails for that negotiation
  2. User can resume a previously paused negotiation from the dashboard, and the agent picks up where it left off
  3. User can stop all negotiations associated with a specific talent agent or agency in one action
  4. Control API endpoints accept pause/resume/stop requests and return confirmation of the state change
**Plans**: TBD

Plans:
- [ ] 21-01: TBD
- [ ] 21-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 18 → 19 → 20 → 21

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7 | v1.0 | 23/23 | Complete | 2026-02-19 |
| 8-12 | v1.1 | 10/10 | Complete | 2026-02-19 |
| 13-17 | v1.2 | 13/13 | Complete | 2026-03-08 |
| 18. Frontend Foundation | 2/2 | Complete    | 2026-03-09 | - |
| 19. Campaign Overview | 2/2 | Complete   | 2026-03-09 | - |
| 20. Negotiation Detail | 2/2 | Complete   | 2026-03-09 | - |
| 21. Negotiation Controls | v1.3 | 0/TBD | Not started | - |
