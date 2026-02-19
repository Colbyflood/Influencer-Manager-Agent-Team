# Roadmap: Influencer Negotiation Agent

## Overview

This roadmap delivers an AI-powered agent that negotiates influencer rates via email using CPM-based pricing logic, operating in hybrid mode with human escalation via Slack. The build progresses from pure domain logic (pricing engine, state machine) through external integrations (Gmail, Google Sheets) to the LLM negotiation pipeline, then Slack human-in-the-loop, and finally campaign data ingestion and operational readiness. Each phase delivers a coherent, testable capability that builds on the previous.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Core Domain and Pricing Engine** - Deterministic pricing logic, negotiation state machine, platform rate cards, and rate boundary enforcement (completed 2026-02-19)
- [x] **Phase 2: Email and Data Integration** - Gmail API send/receive with threading, Google Sheet connection for influencer data, and email parsing (completed 2026-02-19)
- [x] **Phase 3: LLM Negotiation Pipeline** - Intent classification, counter-offer composition, knowledge base integration, and the end-to-end negotiation loop (completed 2026-02-19)
- [x] **Phase 4: Slack and Human-in-the-Loop** - Escalation routing, agreement alerts, human takeover, and configurable trigger rules (completed 2026-02-19)
- [x] **Phase 5: Campaign Ingestion and Operational Readiness** - ClickUp campaign data input, conversation logging, audit trail, and production hardening (completed 2026-02-19)
- [x] **Phase 6: Runtime Orchestration Wiring** - Connect all Phase 1-5 components in app.py: Gmail inbound handler, negotiation loop activation, SlackDispatcher wiring, campaign-to-negotiation handoff, and integration tests (completed 2026-02-19)
- [ ] **Phase 7: Integration Hardening** - Fix graceful degradation bugs, wire inbound email audit logging, activate engagement-quality pricing, and clean up orphaned code paths

## Phase Details

### Phase 1: Core Domain and Pricing Engine
**Goal**: The foundational pricing and state logic exists as tested, deterministic modules that all downstream components depend on
**Depends on**: Nothing (first phase)
**Requirements**: NEG-02, NEG-03, NEG-04, NEG-07
**Success Criteria** (what must be TRUE):
  1. Given an influencer's average views and a deliverable type, the pricing engine returns a rate within the $20-$30 CPM range
  2. The pricing engine correctly handles platform-specific deliverable types (Instagram post/story/reel, TikTok video/story, YouTube dedicated/integration/short) with appropriate rate calculations
  3. A negotiation thread can transition through all defined states (initial_offer, awaiting_reply, counter_received, counter_sent, agreed, rejected, escalated, stale) with invalid transitions rejected
  4. When a proposed rate exceeds the $30 CPM threshold, the system flags it for escalation rather than accepting
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project setup, domain types, enums, and Pydantic models
- [ ] 01-02-PLAN.md — Pricing engine, rate cards, and boundary enforcement (TDD)
- [ ] 01-03-PLAN.md — Negotiation state machine with transition validation (TDD)

### Phase 2: Email and Data Integration
**Goal**: The agent can send and receive emails via Gmail API with proper threading, and read influencer data from Google Sheets to inform pricing decisions
**Depends on**: Phase 1
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, NEG-01, DATA-02
**Success Criteria** (what must be TRUE):
  1. The agent can send an email via Gmail API on behalf of the team and the recipient sees it as part of an existing thread
  2. When an influencer replies to a negotiation email, the agent receives a notification and can read the reply content, correctly parsing it from MIME/inline/forwarded formats
  3. The agent reads an influencer row from the Google Sheet and retrieves the correct pre-calculated pay range based on their metrics
  4. Email thread history is maintained so influencers see a coherent, continuous conversation
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — Dependencies, shared auth module, email and sheets Pydantic models
- [ ] 02-02-PLAN.md — Gmail send/receive, threading, Pub/Sub watch, MIME parsing
- [ ] 02-03-PLAN.md — Google Sheets client with influencer lookup and PayRange bridge

### Phase 3: LLM Negotiation Pipeline
**Goal**: The agent can understand influencer replies, compose intelligent counter-offers guided by a knowledge base, and execute the core negotiation loop end-to-end
**Depends on**: Phase 2
**Requirements**: NEG-05, NEG-06, KB-01, KB-02, KB-03
**Success Criteria** (what must be TRUE):
  1. Given a free-text influencer email reply, the agent correctly extracts rate proposals, deliverable changes, and negotiation intent (accept, counter, reject, question)
  2. The agent composes counter-offer emails that include calculated rates, clear deliverable terms, and appropriate negotiation tone informed by the knowledge base
  3. The knowledge base files are stored in an editable location where the team can update negotiation guidance and best practices without code changes
  4. The end-to-end negotiation loop works: email arrives, intent is classified, pricing engine calculates response rate, LLM composes email, validation gate checks monetary values, email is sent or escalated
**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md — LLM foundation: Anthropic SDK, Pydantic models, knowledge base files and loader
- [ ] 03-02-PLAN.md — Intent classification with structured outputs (TDD)
- [ ] 03-03-PLAN.md — Email composition and deterministic validation gate (TDD)
- [ ] 03-04-PLAN.md — End-to-end negotiation loop orchestrator

### Phase 4: Slack and Human-in-the-Loop
**Goal**: The team receives actionable Slack notifications for escalations and agreements, and can take over any negotiation thread at any time
**Depends on**: Phase 3
**Requirements**: HUMAN-01, HUMAN-02, HUMAN-03, HUMAN-04
**Success Criteria** (what must be TRUE):
  1. When the agent escalates, the Slack message includes full context: conversation history, influencer metrics, proposed vs target rate, and the specific reason for escalation
  2. Escalation triggers fire correctly for all configured rules: CPM over threshold, ambiguous intent, hostile tone, legal/contract language, and unusual deliverable requests
  3. When the influencer agrees to a deal, the team receives a Slack alert with the influencer name, agreed rate, platform, deliverables, CPM achieved, and next steps
  4. When a human responds directly in a negotiation email thread, the agent detects this and stops autonomous handling of that thread
**Plans**: 4 plans

Plans:
- [ ] 04-01-PLAN.md — Dependencies, models (EscalationPayload extension, AgreementPayload), SlackNotifier client, Block Kit builders, YAML trigger config
- [ ] 04-02-PLAN.md — Escalation trigger engine with YAML config loading, deterministic + LLM-based triggers (TDD)
- [ ] 04-03-PLAN.md — Human takeover: Gmail thread detection, thread state management, Slack slash commands (/claim, /resume)
- [ ] 04-04-PLAN.md — SlackDispatcher integration: pre-check gate, escalation/agreement dispatch, negotiation loop wiring

### Phase 5: Campaign Ingestion and Operational Readiness
**Goal**: Campaign data flows in automatically from ClickUp, every negotiation action is logged with a queryable audit trail, and the system is ready for production use
**Depends on**: Phase 4
**Requirements**: DATA-01, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. When a ClickUp form is submitted with campaign details (client info, budget, target deliverables, influencer metrics, CPM range), the agent ingests the data and uses it to guide negotiations
  2. Every sent and received email is logged with timestamps, the current negotiation state, and the rates used in that exchange
  3. The team can query the conversation audit trail by influencer name, campaign, or date range and get a complete history of negotiations
**Plans**: 4 plans

Plans:
- [ ] 05-01-PLAN.md — Dependencies, campaign models, CPM tracker, audit models, SQLite store, resilience retry
- [ ] 05-02-PLAN.md — ClickUp webhook endpoint, campaign ingestion pipeline
- [ ] 05-03-PLAN.md — Audit logger, CLI query interface, Slack /audit command
- [ ] 05-04-PLAN.md — Application entry point, audit wiring, production hardening (FastAPI + Slack Bolt + structlog)

### Phase 6: Runtime Orchestration Wiring
**Goal**: All Phase 1-5 components are connected in the runtime entry point so the agent can receive emails, run the negotiation loop, dispatch Slack notifications, and start negotiations from campaign ingestion — delivering the core value end-to-end
**Depends on**: Phase 5
**Gap Closure**: Closes all 4 integration gaps and 2 broken flows from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. When an influencer replies to a negotiation email, the agent receives the reply (via Gmail Pub/Sub or polling), classifies intent, runs the pricing engine, composes a response, validates it, and either sends or escalates — all without manual intervention
  2. When a ClickUp campaign is ingested with found influencers, the agent retrieves each influencer's PayRange from the Sheet and sends initial outreach emails to start negotiations
  3. SlackDispatcher pre-check gate runs before every negotiation loop iteration — checking human takeover, trigger evaluation, and routing escalations/agreements to Slack
  4. All email sends, receives, escalations, and agreements are logged to the audit trail via the wiring functions
  5. CampaignCPMTracker is instantiated per campaign and provides per-influencer flexibility guidance to the negotiation loop
  6. Deprecated FastAPI on_event pattern is replaced with lifespan handlers
**Plans**: 3 plans

Plans:
- [ ] 06-01-PLAN.md — Lifespan migration, service initialization (GmailClient, SlackDispatcher, Anthropic), Gmail Pub/Sub webhook, inbound email pipeline
- [ ] 06-02-PLAN.md — Campaign-to-negotiation handoff, CampaignCPMTracker wiring, initial outreach emails
- [ ] 06-03-PLAN.md — Integration tests verifying all 4 MISSING gaps and 2 broken flows are closed

### Phase 7: Integration Hardening
**Goal**: Fix graceful degradation bugs, wire missing audit logging, activate engagement-quality pricing, and clean up orphaned code paths discovered by the v1.0 milestone re-audit
**Depends on**: Phase 6
**Gap Closure**: Closes 3 integration issues and 3 tech debt items from v1.0 re-audit
**Success Criteria** (what must be TRUE):
  1. Campaign ingestion works correctly when `SLACK_BOT_TOKEN` is absent — `ingest_campaign` skips Slack notifications gracefully instead of crashing
  2. Inbound emails are logged to the audit trail with timestamps, negotiation state, and rates — completing DATA-03's "every sent/received email" requirement
  3. `InfluencerRow` includes `engagement_rate` field and `CampaignCPMTracker.get_flexibility()` receives real engagement data for premium calculations
  4. Orphaned wiring functions (`create_audited_email_receive`, `get_pay_range` in pipeline) are either connected or explicitly removed
  5. All 681+ tests pass with no regressions
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Domain and Pricing Engine | 3/3 | Complete    | 2026-02-19 |
| 2. Email and Data Integration | 3/3 | Complete    | 2026-02-19 |
| 3. LLM Negotiation Pipeline | 4/4 | Complete    | 2026-02-19 |
| 4. Slack and Human-in-the-Loop | 4/4 | Complete    | 2026-02-19 |
| 5. Campaign Ingestion and Operational Readiness | 4/4 | Complete    | 2026-02-19 |
| 6. Runtime Orchestration Wiring | 3/3 | Complete    | 2026-02-19 |
| 7. Integration Hardening | 0/? | Not started | - |
