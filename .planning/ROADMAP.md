# Roadmap: Influencer Negotiation Agent

## Overview

This roadmap delivers an AI-powered agent that negotiates influencer rates via email using CPM-based pricing logic, operating in hybrid mode with human escalation via Slack. The build progresses from pure domain logic (pricing engine, state machine) through external integrations (Gmail, Google Sheets) to the LLM negotiation pipeline, then Slack human-in-the-loop, and finally campaign data ingestion and operational readiness. Each phase delivers a coherent, testable capability that builds on the previous.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Core Domain and Pricing Engine** - Deterministic pricing logic, negotiation state machine, platform rate cards, and rate boundary enforcement
- [ ] **Phase 2: Email and Data Integration** - Gmail API send/receive with threading, Google Sheet connection for influencer data, and email parsing
- [ ] **Phase 3: LLM Negotiation Pipeline** - Intent classification, counter-offer composition, knowledge base integration, and the end-to-end negotiation loop
- [ ] **Phase 4: Slack and Human-in-the-Loop** - Escalation routing, agreement alerts, human takeover, and configurable trigger rules
- [ ] **Phase 5: Campaign Ingestion and Operational Readiness** - ClickUp campaign data input, conversation logging, audit trail, and production hardening

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
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Email and Data Integration
**Goal**: The agent can send and receive emails via Gmail API with proper threading, and read influencer data from Google Sheets to inform pricing decisions
**Depends on**: Phase 1
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04, NEG-01, DATA-02
**Success Criteria** (what must be TRUE):
  1. The agent can send an email via Gmail API on behalf of the team and the recipient sees it as part of an existing thread
  2. When an influencer replies to a negotiation email, the agent receives a notification and can read the reply content, correctly parsing it from MIME/inline/forwarded formats
  3. The agent reads an influencer row from the Google Sheet and retrieves the correct pre-calculated pay range based on their metrics
  4. Email thread history is maintained so influencers see a coherent, continuous conversation
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: LLM Negotiation Pipeline
**Goal**: The agent can understand influencer replies, compose intelligent counter-offers guided by a knowledge base, and execute the core negotiation loop end-to-end
**Depends on**: Phase 2
**Requirements**: NEG-05, NEG-06, KB-01, KB-02, KB-03
**Success Criteria** (what must be TRUE):
  1. Given a free-text influencer email reply, the agent correctly extracts rate proposals, deliverable changes, and negotiation intent (accept, counter, reject, question)
  2. The agent composes counter-offer emails that include calculated rates, clear deliverable terms, and appropriate negotiation tone informed by the knowledge base
  3. The knowledge base files are stored in an editable location where the team can update negotiation guidance and best practices without code changes
  4. The end-to-end negotiation loop works: email arrives, intent is classified, pricing engine calculates response rate, LLM composes email, validation gate checks monetary values, email is sent or escalated
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: Slack and Human-in-the-Loop
**Goal**: The team receives actionable Slack notifications for escalations and agreements, and can take over any negotiation thread at any time
**Depends on**: Phase 3
**Requirements**: HUMAN-01, HUMAN-02, HUMAN-03, HUMAN-04
**Success Criteria** (what must be TRUE):
  1. When the agent escalates, the Slack message includes full context: conversation history, influencer metrics, proposed vs target rate, and the specific reason for escalation
  2. Escalation triggers fire correctly for all configured rules: CPM over threshold, ambiguous intent, hostile tone, legal/contract language, and unusual deliverable requests
  3. When the influencer agrees to a deal, the team receives a Slack alert with the influencer name, agreed rate, platform, deliverables, CPM achieved, and next steps
  4. When a human responds directly in a negotiation email thread, the agent detects this and stops autonomous handling of that thread
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Campaign Ingestion and Operational Readiness
**Goal**: Campaign data flows in automatically from ClickUp, every negotiation action is logged with a queryable audit trail, and the system is ready for production use
**Depends on**: Phase 4
**Requirements**: DATA-01, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. When a ClickUp form is submitted with campaign details (client info, budget, target deliverables, influencer metrics, CPM range), the agent ingests the data and uses it to guide negotiations
  2. Every sent and received email is logged with timestamps, the current negotiation state, and the rates used in that exchange
  3. The team can query the conversation audit trail by influencer name, campaign, or date range and get a complete history of negotiations
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Domain and Pricing Engine | 0/0 | Not started | - |
| 2. Email and Data Integration | 0/0 | Not started | - |
| 3. LLM Negotiation Pipeline | 0/0 | Not started | - |
| 4. Slack and Human-in-the-Loop | 0/0 | Not started | - |
| 5. Campaign Ingestion and Operational Readiness | 0/0 | Not started | - |
