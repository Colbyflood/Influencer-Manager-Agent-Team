# Project Research Summary

**Project:** Influencer Manager Agent Team
**Domain:** AI-powered email negotiation agent for influencer marketing
**Researched:** 2026-02-18
**Confidence:** MEDIUM

## Executive Summary

This project is an AI-powered agent that automates influencer rate negotiation via email, operating in a hybrid autonomous/human mode. The product fills a genuine gap: influencer marketing platforms (GRIN, AspireIQ, CreatorIQ) manage relationships but leave negotiation to humans, while email automation tools (Instantly, Smartlead) handle sequences but have zero understanding of rates or negotiation strategy. No existing tool automates the actual negotiation conversation with CPM-based decision logic. The recommended approach is a Python-based LangGraph agent backed by PostgreSQL, with Gmail API for email, Slack for human-in-the-loop escalation, and ClickUp for campaign data ingestion. Claude Sonnet serves as the primary LLM for intent classification and email composition, but critically, the LLM must never be the source of truth for pricing -- deterministic code handles all rate calculations and boundary enforcement.

The architecture follows an event-driven, stateful agent pattern. Incoming emails trigger events routed to a negotiation agent built on a finite state machine. The agent uses a pricing engine (deterministic CPM math), an LLM pipeline (structured output for intent analysis and email drafting), and an escalation router (allowlist-based, not blocklist). Every external service sits behind a gateway abstraction (ports and adapters), making the system testable and extensible to future agents. The most important architectural decision is that negotiation state lives in the database as a state machine, not in the LLM's context window -- this prevents the most common class of agent failures (state corruption, hallucinated commitments, lost context in long threads).

The primary risks are: (1) LLM hallucinating rates or commitments in sent emails -- mitigated by a hard validation gate that blocks any email containing out-of-range monetary values, (2) email threading corruption causing the agent to lose track of negotiation state -- mitigated by an explicit database-backed state machine, (3) Gmail deliverability collapse from automated sending patterns -- mitigated by dedicated sending accounts, SPF/DKIM/DMARC, rate limiting, and gradual warm-up, and (4) the agent acting autonomously when it should escalate -- mitigated by an inverted escalation model where the agent needs an allowlist of things it CAN do, and everything else escalates to humans.

## Key Findings

### Recommended Stack

Python 3.12+ with LangGraph for agent orchestration, FastAPI for webhooks, PostgreSQL for persistence, and Redis + Celery for background task processing. The stack is Python-first because the AI/ML agent ecosystem (LangGraph, LangChain, Anthropic SDK) has Python as its primary target -- TypeScript alternatives lag in maturity and community support. LangGraph was chosen over CrewAI (overkill for single-agent v1), AutoGen (wrong paradigm for email-based negotiation), and raw SDK (would require reimplementing state management, persistence, and human-in-the-loop patterns).

**Core technologies:**
- **LangGraph (~0.2.x):** Agent orchestration -- purpose-built for stateful, multi-step AI workflows with human-in-the-loop interrupt/resume patterns. Supports future multi-agent expansion via subgraphs.
- **Claude Sonnet (3.5/4):** Primary LLM -- best instruction-following for structured negotiation tasks at a cost-effective tier. LangGraph makes model swapping trivial if needed.
- **FastAPI (~0.115.x):** HTTP layer -- async-native, auto-generated OpenAPI docs, handles Gmail push notifications, ClickUp webhooks, and Slack interactivity endpoints.
- **PostgreSQL 16+:** Primary data store + LangGraph state persistence (via langgraph-checkpoint-postgres). JSONB handles semi-structured deliverable data. Relational model fits the campaign/influencer/negotiation domain.
- **Gmail API (google-api-python-client):** Email integration -- thread-level operations, push notifications, and label management. SMTP/IMAP cannot reliably track threads. Non-negotiable.
- **Slack Bolt (~1.20.x):** Escalation and alerts -- interactive messages with approve/reject buttons. The team already lives in Slack.
- **Celery (~5.4.x) + Redis 7.x:** Background task queue -- email sending, Slack notifications, and ClickUp syncing must be async to prevent blocking the agent loop.

**Critical version note:** All version numbers are from training data (cutoff May 2025). Verify against current releases before locking in, especially LangGraph (fast-moving) and langchain-anthropic compatibility.

### Expected Features

**Must have (table stakes):**
- Gmail API email send/receive with threading -- the entire system depends on this
- CPM-based rate calculation engine with viral outlier exclusion -- the brain of negotiation logic
- Multi-turn negotiation state machine (initial offer, counter, acceptance, rejection, escalation, stale)
- LLM-based counter-offer parsing (extract rates, deliverables, intent from free-text email)
- Multi-platform deliverable support (Instagram, TikTok, YouTube with different pricing norms)
- Email template system with personalization (initial offer, counter, acceptance, follow-up)
- Rate boundary enforcement (hard $30 CPM ceiling, auto-escalate above threshold)
- Human escalation via Slack with full context and one-click approve
- Agreement detection and structured Slack notification
- Conversation audit trail (every email, every state transition, every LLM analysis)
- Campaign data input (JSON/manual for v1; ClickUp integration follows)

**Should have (add after core loop is validated):**
- ClickUp integration for automated campaign data ingestion
- Stale negotiation detection and automated follow-up sequences
- Negotiation playbook configuration (per-client strategies: speed vs. price)
- Intelligent counter-offer strategy (beyond split-the-difference)
- Confidence scoring for agreement detection (reduce false positives)

**Defer (v2+):**
- Rate memory across negotiations, negotiation analytics, multi-deliverable CPM optimization, usage rights pricing calculator, negotiation style adaptation, deliverable bundling/unbundling
- Anti-features to never build in v1: fully autonomous mode (no human escalation), live metric pulling, AI cold outreach, contract generation, real-time DM negotiation, multi-language, automatic budget allocation

### Architecture Approach

The system follows an event-driven architecture with a finite state machine per negotiation thread, gateway abstractions for all external services (hexagonal/ports-and-adapters), and an LLM prompt pipeline with structured output and hard validation gates. The architecture is designed for single-agent v1 but is explicitly extensible to multi-agent via LangGraph subgraphs and the agent registry pattern.

**Major components:**
1. **Email Gateway** -- Gmail API abstraction for send/receive/threading; future-proofed behind an interface for provider swapping
2. **Pricing Engine** -- Pure deterministic module for CPM calculations, outlier exclusion, threshold checks; LLM never touches pricing math
3. **Negotiation State Machine** -- Database-persisted FSM tracking the lifecycle of each thread (9 states, guarded transitions)
4. **Response Composer** -- LLM prompt pipeline: builds context from structured negotiation state (not raw emails), calls LLM for intent classification and email drafting, validates output against schemas and business rules
5. **Escalation Router** -- Allowlist-based: defines what the agent CAN do, escalates everything else. Packages full context for Slack with draft response and approve/reject buttons
6. **Event Router** -- Dispatches incoming events (new email, campaign created, human response, timeout) to appropriate handlers; decouples triggers from logic

### Critical Pitfalls

1. **LLM hallucinating rates and commitments** -- The LLM must never compute or choose rates. All pricing comes from the deterministic Pricing Engine. A post-generation validation gate must extract every monetary value from draft emails and block sending if any value falls outside the authorized range. Zero tolerance.

2. **Email thread state corruption** -- Maintain an explicit state machine in the database, not derived from email content. Parse and classify each incoming email before the LLM sees it. Pass structured negotiation state to the LLM, not raw messy email threads. Set a maximum thread depth (6 exchanges) before auto-escalation.

3. **Gmail deliverability collapse** -- Use a dedicated Workspace sending account, configure SPF/DKIM/DMARC before sending any emails, implement application-level rate limiting (1 email/minute max), track delivery success, warm up the account gradually, and implement a circuit breaker that pauses sending after 3+ failures.

4. **Agent acts when it should escalate** -- Invert the escalation model: define a narrow allowlist of what the agent IS authorized to do (propose rates in CPM range, accept within range, decline and counter, ask clarifying questions about deliverables/timeline). Everything else escalates by default. Require LLM confidence score above 0.8 to act; below that, auto-escalate.

5. **Platform/format pricing equivalence** -- Do not use a single CPM range for all deliverables. Build a rate card system with per-platform, per-format ranges (Instagram Story $8-$15 CPM vs. YouTube long-form $30-$50 CPM). Usage rights need a separate pricing multiplier. Without this, the agent systematically overpays on cheap formats and loses deals on premium ones.

## Implications for Roadmap

Based on the combined research, the project has clear dependency layers that dictate a natural build order. The architecture research identifies 5 build phases, the features research defines P1/P2/P3 priority tiers, and the pitfalls research maps prevention to specific phases. Here is the synthesized recommendation:

### Phase 1: Foundation and Core Domain

**Rationale:** Everything depends on domain types, the state machine, the pricing engine, and configuration. These are pure logic modules with zero external dependencies and can be fully unit-tested. The architecture research identifies this as the zero-dependency layer. The pitfalls research demands that rate validation and state management be architecturally enforced from day one -- not bolted on later.

**Delivers:** Core domain types (Campaign, Influencer, Negotiation, Deliverable), finite state machine for negotiation lifecycle, CPM-based pricing engine with outlier detection and per-platform rate cards, rate boundary enforcement, event router, configuration schema, error types, project skeleton with uv, ruff, mypy, and pre-commit.

**Features addressed:** CPM rate calculation engine, multi-platform deliverable pricing, rate boundary enforcement, negotiation state machine (core logic), conversation audit trail (data models).

**Pitfalls avoided:** LLM hallucinating rates (pricing engine is deterministic from day one), email thread state corruption (state machine is database-backed), platform/format pricing equivalence (rate cards are per-platform from the start).

### Phase 2: Email Integration and Data Layer

**Rationale:** Email is the foundational I/O channel -- nothing works without the ability to send and receive. The architecture demands gateway abstractions for all external services, so this phase builds the email gateway interface and Gmail implementation, plus the full database access layer. Gmail deliverability pitfalls must be addressed here before any automated sending begins.

**Delivers:** Email gateway interface and Gmail API implementation (send, receive, threading, MIME parsing), database schema and repository layer (PostgreSQL + SQLAlchemy + Alembic), OAuth token management with refresh handling, email delivery tracking, SPF/DKIM/DMARC verification, sending rate limiter, circuit breaker.

**Features addressed:** Gmail API email send/receive with threading, email template system, conversation audit trail (persistence).

**Pitfalls avoided:** Gmail deliverability collapse (dedicated account, authentication records, rate limiting, delivery tracking), OAuth token expiry (refresh handling with alerting).

### Phase 3: LLM Pipeline and Negotiation Agent

**Rationale:** With the pricing engine and email gateway in place, the agent can now be assembled. This phase wires the LLM pipeline (intent classification, response composition) to the state machine and pricing engine. The escalation router is built here with the inverted allowlist model. This is where the core negotiation loop becomes functional end-to-end.

**Delivers:** LLM client wrapper (Anthropic SDK with structured output, retries, token limits), intent classifier (counter, accept, reject, question, unclear), response composer (stage-specific prompts for initial offer, counter, acceptance, follow-up), post-generation validation gate (extract and verify all monetary values), escalation router with allowlist model, end-to-end negotiation loop (email in -> classify -> price -> compose -> validate -> send or escalate).

**Features addressed:** Counter-offer parsing (LLM-based), negotiation state machine (full integration), escalation trigger rules, agreement detection.

**Pitfalls avoided:** Agent acts when it should escalate (allowlist model), prompt injection (two-LLM classifier/responder pattern + output validation gate), LLM hallucinating commitments (validation gate blocks out-of-range values).

### Phase 4: Slack Integration and Human-in-the-Loop

**Rationale:** The agent can now negotiate autonomously within bounds. This phase adds the critical human escalation circuit: Slack notifications with full context and actionable buttons, human approval/modification/takeover flow, and the feedback loop from human decisions back to the agent.

**Delivers:** Slack gateway (Bolt framework), rich escalation messages with Block Kit (influencer context, draft response, approve/reject/takeover buttons), agreement notification messages, human response routing back through the event system, escalation timeout handling, agent status reporting via Slack.

**Features addressed:** Human escalation via Slack, agreement detection and Slack alert, human takeover capability.

**Pitfalls avoided:** No escalation boundary (allowlist enforced from Phase 3, Slack UI enables human override), escalation messages without context (Block Kit with full negotiation summary and draft).

### Phase 5: Campaign Ingestion, Operational Hardening, and Launch

**Rationale:** The core negotiation loop is functional with human-in-the-loop. Now connect the campaign data pipeline (ClickUp integration), add background task processing (Celery), implement stale negotiation follow-up, and harden the system for production. This phase transitions from "it works" to "it works reliably at scale."

**Delivers:** Campaign data input (ClickUp webhook integration, manual JSON fallback), Celery task queue for async email processing, stale negotiation detection and follow-up sequences, error recovery and queue management, end-to-end integration tests, prompt injection red-teaming, full-flow testing with real email threads.

**Features addressed:** Campaign data input, ClickUp integration, stale negotiation follow-up.

**Pitfalls avoided:** Synchronous LLM calls blocking webhooks (Celery async processing), escalation flood (rate-limited Slack messages), "looks done but isn't" (comprehensive end-to-end testing checklist).

### Phase 6: Advanced Negotiation and Multi-Agent Foundation

**Rationale:** With a proven, reliable core loop, add advanced features that optimize negotiation outcomes and lay the foundation for future agents (outreach agent, strategist agent).

**Delivers:** Configurable negotiation playbooks (per-client strategies), intelligent counter-offer strategy (anchoring, concession patterns), confidence scoring for agreement detection, rate memory across negotiations, agent registry for multi-agent extensibility, negotiation analytics (Slack-based reports).

**Features addressed:** Intelligent counter-offer strategy, negotiation playbook configuration, confidence scoring, rate memory, negotiation analytics.

### Phase Ordering Rationale

- **Phase 1 before everything:** The pricing engine and state machine are dependencies for every subsequent phase. Building them first with zero external dependencies means they can be fully unit-tested and hardened before any integration complexity enters the picture. This directly prevents the top two pitfalls (hallucinated rates, state corruption).
- **Phase 2 before Phase 3:** The LLM pipeline (Phase 3) needs to send emails. Building the email gateway first means Phase 3 can focus purely on agent logic, not email plumbing. Gmail deliverability issues take weeks to surface -- starting email infrastructure early gives time to detect problems.
- **Phase 3 is the integration crux:** This is where all components wire together. It is the highest-risk phase and benefits from solid, tested foundations in Phases 1 and 2. The escalation router and validation gate must be correct here -- they are the safety rails for the entire system.
- **Phase 4 after the agent works:** Slack integration depends on having a working agent that produces escalation events and agreement events. Building Slack first would mean testing with fake data; building the agent first means Slack integration tests against real agent output.
- **Phase 5 is operational readiness:** ClickUp integration and Celery async processing are not needed until the core loop is validated. The agent can be tested with hardcoded campaign data while this is built.
- **Phase 6 last:** Advanced negotiation features require a proven baseline. Intelligent counter-offer strategy, style adaptation, and bundling are optimizations on top of a working system.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Email Integration):** Gmail API push notifications via Google Cloud Pub/Sub require specific GCP setup. OAuth2 token management and scope requirements need verification against current Google documentation. MIME parsing edge cases (mobile HTML-only replies, inline images, forwarded threads) need real-world test data.
- **Phase 3 (LLM Pipeline):** LangGraph's human-in-the-loop interrupt/resume patterns and langgraph-checkpoint-postgres configuration need verification against current LangGraph docs (fast-moving API). Structured output schemas for intent classification and response composition need prompt engineering iteration. The two-LLM classifier/responder architecture for prompt injection defense needs validation.
- **Phase 6 (Advanced Negotiation):** Intelligent counter-offer strategy requires research into negotiation theory (anchoring, concession curves, BATNA). Market-rate CPM data per platform/format needs current validation -- training data rates may be outdated.

Phases with standard patterns (skip deep research):
- **Phase 1 (Foundation):** State machines, pricing engines, and domain modeling are well-documented patterns. No novel technical challenges.
- **Phase 4 (Slack Integration):** Standard Slack Bolt patterns, well-documented Block Kit components. Unlikely to need additional research.
- **Phase 5 (Campaign Ingestion):** ClickUp webhook integration, Celery task queues, and operational tooling follow established patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Architectural patterns (LangGraph, FastAPI, PostgreSQL) are HIGH confidence. Exact version numbers and API compatibility are MEDIUM -- all based on training data cutoff May 2025. LangGraph is fast-moving; verify versions before implementation. |
| Features | MEDIUM | Feature landscape and priorities are well-grounded in project requirements and competitive analysis. Competitor feature sets could not be verified against live product pages. CPM market rates ($20-$30 range) are per project spec, not independently validated. |
| Architecture | MEDIUM-HIGH | Core patterns (event-driven, state machine, ports/adapters, structured LLM output) are fundamental, well-established patterns with HIGH confidence. Integration-specific details (Gmail push notifications, Slack Bolt interactive messages, LangGraph checkpoint persistence) are MEDIUM. |
| Pitfalls | MEDIUM-HIGH | Pitfall categories (LLM hallucination, email deliverability, state corruption, prompt injection) are well-documented in the AI agent and email automation communities. Specific Gmail API quotas and LLM pricing should be verified. |

**Overall confidence:** MEDIUM

The research provides a strong architectural foundation and clear build order. The primary uncertainty is in version-specific details (LangGraph API, Gmail quotas, Anthropic SDK structured output) that need verification against current documentation during implementation. The domain-level recommendations (event-driven architecture, deterministic pricing engine, allowlist escalation model, database-backed state machine) are high confidence and should be treated as non-negotiable architectural decisions.

### Gaps to Address

- **Current LangGraph version and API surface:** Verify LangGraph ~0.2.x API, human-in-the-loop patterns, and langgraph-checkpoint-postgres compatibility against current docs before Phase 3 planning.
- **Gmail API quotas and push notification setup:** Verify current sending limits, quota units, and Pub/Sub push notification configuration before Phase 2 implementation. GCP project setup may be required.
- **Platform-specific CPM market rates:** The $20-$30 CPM range comes from project requirements. Real market data is needed to determine if this range is appropriate for all platforms and deliverable types. Instagram Stories and YouTube long-form have very different market norms.
- **Anthropic SDK structured output patterns:** Verify current tool_use / structured output API for Claude Sonnet before Phase 3. The exact pattern for enforcing JSON schema output may have changed.
- **Slack interactive message limitations:** Verify current Block Kit capabilities, message action payload format, and rate limits for interactive messages before Phase 4.
- **Email MIME parsing edge cases:** Need real-world email samples from actual influencer negotiations to build robust parsing. Mobile HTML-only replies, forwarded threads, inline images, and CC'd party messages are common edge cases that cannot be anticipated from documentation alone.

## Sources

### Primary (HIGH confidence)
- Hexagonal architecture / ports and adapters pattern -- well-established, not version-dependent
- Finite state machine patterns for multi-turn conversation agents -- fundamental CS pattern
- Event-driven architecture for async email processing -- established pattern
- Email deliverability standards (SPF/DKIM/DMARC) -- long-standing infrastructure standards
- OWASP LLM Top 10 for prompt injection risks -- industry standard reference

### Secondary (MEDIUM confidence)
- LangGraph documentation and architecture patterns (training data, cutoff May 2025)
- Gmail API documentation (thread management, OAuth, push notifications)
- Slack API documentation (Block Kit, interactive messages, Bolt framework)
- Anthropic Claude API documentation (tool use, structured output)
- FastAPI + SQLAlchemy + PostgreSQL patterns (mature, stable technologies)
- Influencer marketing platform feature analysis (GRIN, AspireIQ, CreatorIQ, Instantly, Smartlead)

### Tertiary (LOW confidence)
- Exact library version numbers throughout (training data only -- must verify all before locking in)
- Influencer marketing CPM benchmarks by platform/format (market rates shift; $20-$30 range per project spec, not independently validated)
- ClickUp API v2 current capabilities (verify at https://clickup.com/api)
- uv package manager maturity and production-readiness (relatively new tool in training data)

---
*Research completed: 2026-02-18*
*Ready for roadmap: yes*
