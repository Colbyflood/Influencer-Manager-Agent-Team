# Roadmap: Influencer Negotiation Agent

## Milestones

- v1.0 MVP -- Phases 1-7 (shipped 2026-02-19)
- v1.1 Production Readiness -- Phases 8-12 (shipped 2026-02-19)
- v1.2 Real-World Negotiation Intelligence -- Phases 13-17 (in progress)

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

<details>
<summary>v1.1 Production Readiness (Phases 8-12) -- SHIPPED 2026-02-19</summary>

- [x] Phase 8: Settings and Health Infrastructure (2/2 plans) -- completed 2026-02-19
- [x] Phase 9: Persistent Negotiation State (2/2 plans) -- completed 2026-02-19
- [x] Phase 10: Docker Packaging and Deployment (2/2 plans) -- completed 2026-02-19
- [x] Phase 11: CI/CD Pipeline (1/1 plan) -- completed 2026-02-19
- [x] Phase 12: Monitoring, Observability, and Live Verification (3/3 plans) -- completed 2026-02-19

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

### v1.2 Real-World Negotiation Intelligence (In Progress)

**Milestone Goal:** Align the agent with real-world campaign data, negotiation strategy, and counterparty awareness so it can handle actual AGM negotiations using the full ClickUp form fields and proven tactics.

- [x] **Phase 13: Campaign Data Model Expansion** - Ingest and parse all 42 ClickUp form fields into a rich campaign model with goals, deliverable scenarios, usage rights, budget constraints, and product leverage (completed 2026-03-08)
- [x] **Phase 14: Knowledge Base Rewrite** - Replace placeholder knowledge base with real AGM negotiation playbook, strategy docs, and categorized email examples (completed 2026-03-08)
- [x] **Phase 15: Negotiation Levers and Strategy** - Implement the full negotiation lever stack: deliverable tiers, usage rights trading, product offers, CPM sharing, cost bounds enforcement, and graceful exits (completed 2026-03-08)
- [ ] **Phase 16: Counterparty Intelligence** - Detect influencer vs talent manager/agency from email signals and adapt negotiation tone and tracking accordingly
- [ ] **Phase 17: Email Composition and Style** - Compose emails matching AGM professional style with structured SOW counter-offers, payment terms, and stage-aware example selection

## Phase Details

### Phase 13: Campaign Data Model Expansion
**Goal**: Agent understands the full scope of a campaign from ClickUp form data, giving every downstream negotiation lever the data it needs
**Depends on**: Phase 12 (v1.1 complete)
**Requirements**: CAMP-01, CAMP-02, CAMP-03, CAMP-04, CAMP-05, CAMP-06, CAMP-07, CAMP-08
**Success Criteria** (what must be TRUE):
  1. Agent accepts a ClickUp webhook with all 42 form fields and persists a complete campaign record without data loss
  2. Agent exposes parsed deliverable scenarios (3 tiers), usage rights (target and minimum with durations), and budget constraints (floor, ceiling, CPM target + leniency) as structured data accessible to negotiation logic
  3. Agent uses per-campaign CPM Target and CPM Leniency percentage to calculate rate boundaries instead of the hardcoded $20-$30 range
  4. Agent parses product leverage fields (availability, description, monetary value) and campaign requirements (exclusivity, approval terms, dates) into queryable campaign attributes
**Plans**: 3 plans
Plans:
- [x] 13-01-PLAN.md -- Expand Campaign model with sub-models for all 42 fields
- [ ] 13-02-PLAN.md -- Update ingestion pipeline for full 42-field parsing
- [ ] 13-03-PLAN.md -- Wire per-campaign CPM target and leniency into pricing engine

### Phase 14: Knowledge Base Rewrite
**Goal**: Agent has access to real AGM negotiation strategy and email examples so it can compose responses grounded in proven tactics rather than generic templates
**Depends on**: Nothing (independent content work, no code dependencies)
**Requirements**: KB-04, KB-05, KB-06
**Success Criteria** (what must be TRUE):
  1. Knowledge base contains a negotiation playbook documenting AGM standards, available levers (deliverable tiers, usage rights, product, CPM sharing), and budget maximization strategy
  2. Knowledge base contains at least 6 real email examples covering: positive close, escalation, walk-away, bundled rate, CPM mention, and misalignment exit scenarios
  3. Agent selects relevant email examples as style reference based on current negotiation stage and scenario (e.g., counter-offer stage gets bundled rate example, not close example)
**Plans**: 2 plans
Plans:
- [ ] 14-01-PLAN.md -- Rewrite KB with AGM negotiation playbook and categorized email examples
- [ ] 14-02-PLAN.md -- Add stage-aware example selection to KB loader and wire into callers

### Phase 15: Negotiation Levers and Strategy
**Goal**: Agent negotiates using the full lever stack -- opening high, trading deliverables and usage rights downward, offering product value, enforcing cost bounds, and exiting gracefully when deals don't work
**Depends on**: Phase 13 (needs expanded campaign data fields)
**Requirements**: NEG-08, NEG-09, NEG-10, NEG-11, NEG-12, NEG-13, NEG-14, NEG-15
**Success Criteria** (what must be TRUE):
  1. Agent opens negotiations requesting more deliverables at a lower rate than budget allows, creating concession room
  2. Agent trades deliverable tiers downward (scenario 1 to 2 to 3) and usage rights duration downward (target to minimum) as cost-reduction levers when influencer rate exceeds budget
  3. Agent offers product/upgrade as additional value when cash rate is at ceiling, and can propose content syndication (cross-posting) as added value instead of unique per-platform deliverables
  4. Agent enforces per-influencer cost floor (never offers below minimum) and escalates to human when rate exceeds max-without-approval ceiling
  5. Agent initiates a polite exit preserving the relationship when deal economics don't work, and can selectively share CPM target with motivated influencers to justify constraints
**Plans**: 3 plans
Plans:
- [ ] 15-01-PLAN.md -- Lever engine models and deterministic selection logic (TDD)
- [ ] 15-02-PLAN.md -- Wire lever engine into negotiation loop, composer, and prompts
- [ ] 15-03-PLAN.md -- Pass campaign data through context builder and lever-driven initial outreach

### Phase 16: Counterparty Intelligence
**Goal**: Agent identifies who it is negotiating with and adapts its approach -- transactional and data-backed for talent managers, relationship-driven for direct influencers
**Depends on**: Phase 13 (needs campaign context for thread tracking)
**Requirements**: CPI-01, CPI-02, CPI-03, CPI-04
**Success Criteria** (what must be TRUE):
  1. Agent detects whether email counterparty is an influencer or talent manager/agency based on email signatures, domain patterns, and thread context
  2. Agent tracks agency name and multiple contacts per negotiation thread (e.g., manager + assistant) without losing negotiation state
  3. Agent uses a more transactional, data-backed tone with talent managers and a more relationship-driven, creative-alignment tone with direct influencers
  4. Agent handles multi-person threads where a manager loops in an assistant or the influencer without losing context or restarting negotiation
**Plans**: 3 plans
Plans:
- [ ] 16-01-PLAN.md -- Counterparty detection models and classifier (TDD)
- [ ] 16-02-PLAN.md -- Contact tracking and multi-person thread wiring into app pipeline
- [ ] 16-03-PLAN.md -- Tone adjustment module wired into composer and negotiation loop

### Phase 17: Email Composition and Style
**Goal**: Agent composes emails that look and feel like real AGM negotiation emails -- professional but warm, with structured SOW counter-offers and clear next steps
**Depends on**: Phase 14 (needs knowledge base examples), Phase 15 (needs negotiation levers for SOW content)
**Requirements**: EMAIL-05, EMAIL-06, EMAIL-07
**Success Criteria** (what must be TRUE):
  1. Agent composes emails with professional but warm tone matching AGM style: partnership-first language, acknowledgment of creator value, concise structure
  2. Agent formats counter-offers with clear SOW structure including deliverable list, usage terms, and rate with strikethrough adjustments matching real AGM email format
  3. Agent includes payment terms and explicit next steps in agreement confirmation emails
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 13 and 14 (14 has no dependency on 13), then 15, 16, 17.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Domain and Pricing Engine | v1.0 | 3/3 | Complete | 2026-02-19 |
| 2. Email and Data Integration | v1.0 | 3/3 | Complete | 2026-02-19 |
| 3. LLM Negotiation Pipeline | v1.0 | 4/4 | Complete | 2026-02-19 |
| 4. Slack and Human-in-the-Loop | v1.0 | 4/4 | Complete | 2026-02-19 |
| 5. Campaign Ingestion and Operational Readiness | v1.0 | 4/4 | Complete | 2026-02-19 |
| 6. Runtime Orchestration Wiring | v1.0 | 3/3 | Complete | 2026-02-19 |
| 7. Integration Hardening | v1.0 | 2/2 | Complete | 2026-02-19 |
| 8. Settings and Health Infrastructure | v1.1 | 2/2 | Complete | 2026-02-19 |
| 9. Persistent Negotiation State | v1.1 | 2/2 | Complete | 2026-02-19 |
| 10. Docker Packaging and Deployment | v1.1 | 2/2 | Complete | 2026-02-19 |
| 11. CI/CD Pipeline | v1.1 | 1/1 | Complete | 2026-02-19 |
| 12. Monitoring, Observability, and Live Verification | v1.1 | 3/3 | Complete | 2026-02-19 |
| 13. Campaign Data Model Expansion | 3/3 | Complete    | 2026-03-08 | - |
| 14. Knowledge Base Rewrite | 2/2 | Complete    | 2026-03-08 | - |
| 15. Negotiation Levers and Strategy | 3/3 | Complete    | 2026-03-08 | - |
| 16. Counterparty Intelligence | v1.2 | 0/3 | Not started | - |
| 17. Email Composition and Style | v1.2 | 0/? | Not started | - |
