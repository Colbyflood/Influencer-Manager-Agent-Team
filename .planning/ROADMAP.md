# Roadmap: Influencer Negotiation Agent

## Milestones

- ✅ **v1.0 MVP** - Phases 1-7 (shipped 2026-02-19)
- ✅ **v1.1 Production Readiness** - Phases 8-12 (shipped 2026-02-19)
- ✅ **v1.2 Real-World Negotiation Intelligence** - Phases 13-17 (shipped 2026-03-08)
- ✅ **v1.3 Campaign Dashboard** - Phases 18-21 (shipped 2026-03-09)
- 🚧 **v1.4 Per-Campaign Influencer Sheets** - Phases 22-23 (in progress)

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

<details>
<summary>v1.3 Campaign Dashboard (Phases 18-21) -- SHIPPED 2026-03-09</summary>

- [x] Phase 18: Frontend Foundation (2/2 plans) -- completed 2026-03-09
- [x] Phase 19: Campaign Overview (2/2 plans) -- completed 2026-03-09
- [x] Phase 20: Negotiation Detail (2/2 plans) -- completed 2026-03-09
- [x] Phase 21: Negotiation Controls (2/2 plans) -- completed 2026-03-09

Full details: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

</details>

### v1.4 Per-Campaign Influencer Sheets (In Progress)

**Milestone Goal:** Replace the single global influencer sheet with per-campaign sheet tabs (or separate spreadsheets), monitor for newly added influencers mid-campaign, and auto-start negotiations for them.

- [x] **Phase 22: Per-Campaign Sheet Routing** - Campaign model, ClickUp parsing, and SheetsClient all use per-campaign tab/sheet instead of hardcoded "Sheet1" (completed 2026-03-09)
- [x] **Phase 23: Sheet Monitoring and Auto-Negotiation** - Hourly polling detects new influencer rows, auto-starts negotiations, alerts on modifications, and prevents duplicate outreach (completed 2026-03-10)

## Phase Details

### Phase 22: Per-Campaign Sheet Routing
**Goal**: Each campaign reads influencer data from its own sheet tab (or separate spreadsheet) instead of the hardcoded global "Sheet1"
**Depends on**: Phase 21 (v1.3 complete)
**Requirements**: SHEET-01, SHEET-02, SHEET-03, INGEST-01, INGEST-02, INGEST-03
**Success Criteria** (what must be TRUE):
  1. When a ClickUp form includes a sheet tab name, the campaign uses that tab to find influencers
  2. When a ClickUp form includes a separate spreadsheet URL/ID, the campaign reads from that spreadsheet instead of the master sheet
  3. When no tab name or spreadsheet override is provided, the campaign defaults to the master spreadsheet with reasonable tab behavior
  4. The existing negotiation pipeline works identically regardless of which sheet/tab the influencer data came from
**Plans**: 2 plans

Plans:
- [ ] 22-01-PLAN.md -- Campaign model + ClickUp config + SheetsClient override support
- [ ] 22-02-PLAN.md -- Ingestion pipeline wiring and per-campaign routing tests

### Phase 23: Sheet Monitoring and Auto-Negotiation
**Goal**: The system continuously watches each active campaign's sheet tab for changes and automatically acts on new or modified influencer rows
**Depends on**: Phase 22
**Requirements**: MON-01, MON-02, MON-03, MON-04
**Success Criteria** (what must be TRUE):
  1. When a new influencer row is added to a campaign's sheet tab after initial ingestion, the agent detects it within the next polling cycle (hourly)
  2. Newly discovered influencers automatically enter the negotiation pipeline without manual intervention
  3. When an existing influencer's row is modified after their negotiation has started, the team receives a Slack alert with the change details
  4. An influencer row that has already been processed is never sent through outreach a second time
**Plans**: 2 plans

Plans:
- [ ] 23-01-PLAN.md -- SheetMonitor core: processed-row tracking, diff detection, dedup logic
- [ ] 23-02-PLAN.md -- Async polling loop, auto-negotiation trigger, modification alerts, app.py wiring

## Progress

**Execution Order:**
Phases execute in numeric order: 22 → 23

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-7 | v1.0 | 23/23 | Complete | 2026-02-19 |
| 8-12 | v1.1 | 10/10 | Complete | 2026-02-19 |
| 13-17 | v1.2 | 13/13 | Complete | 2026-03-08 |
| 18-21 | v1.3 | 8/8 | Complete | 2026-03-09 |
| 22. Per-Campaign Sheet Routing | 2/2 | Complete    | 2026-03-09 | - |
| 23. Sheet Monitoring and Auto-Negotiation | 2/2 | Complete    | 2026-03-10 | - |
