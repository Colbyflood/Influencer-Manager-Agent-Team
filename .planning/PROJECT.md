# Influencer Negotiation Agent

## What This Is

An AI-powered agent that handles influencer rate negotiations via email on behalf of marketing teams. The agent picks up email threads where influencers have already responded to outreach, negotiates deliverable rates using CPM-based pricing logic ($20-$30 CPM range), and alerts the team via Slack when agreements are reached or escalation is needed. It operates in hybrid mode — autonomously handling routine negotiation while escalating edge cases to humans.

## Core Value

The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome — every agreed deal must result in a clear, actionable Slack notification to the team.

## Current State

**Shipped:** v1.0 MVP (2026-02-19)
**Codebase:** 6,799 LOC source + 9,595 LOC tests (Python)
**Tests:** 691 passing
**Tech stack:** Python 3.12+, FastAPI, Anthropic SDK, Gmail API, Google Sheets API, Slack Bolt, SQLite, Pydantic v2

The system can:
1. Receive inbound emails via Gmail Pub/Sub and run the full negotiation pipeline
2. Ingest campaigns from ClickUp and start negotiations for found influencers
3. Classify intent and compose counter-offers using LLM with knowledge base guidance
4. Escalate edge cases to Slack with full context (configurable triggers)
5. Detect agreement and notify the team with actionable alerts
6. Support human takeover of any thread
7. Log all actions to a queryable SQLite audit trail (CLI + Slack)

## Requirements

### Validated

- ✓ EMAIL-01: Agent can send emails via Gmail API on behalf of the team — v1.0
- ✓ EMAIL-02: Agent can receive and process inbound emails via Gmail API with push notifications — v1.0
- ✓ EMAIL-03: Agent maintains email thread context so influencers see a coherent conversation history — v1.0
- ✓ EMAIL-04: Agent can parse influencer reply content from email threads (MIME, inline, forwarding) — v1.0
- ✓ NEG-01: Agent reads influencer data from Google Sheet and pulls proposed pay range based on CPM — v1.0
- ✓ NEG-02: Agent uses pre-calculated pay range to guide negotiation ($20 floor to $30 ceiling CPM) — v1.0
- ✓ NEG-03: Agent supports platform-specific deliverable pricing (Instagram, TikTok, YouTube) — v1.0
- ✓ NEG-04: Agent tracks negotiation state across multi-turn conversations — v1.0
- ✓ NEG-05: Agent extracts rate proposals and intent from free-text email replies using LLM — v1.0
- ✓ NEG-06: Agent composes counter-offer emails with calculated rates and clear terms — v1.0
- ✓ NEG-07: Agent enforces rate boundaries and escalates when demands exceed $30 CPM — v1.0
- ✓ HUMAN-01: Agent escalates to Slack with full context — v1.0
- ✓ HUMAN-02: Agent escalates based on configurable trigger rules — v1.0
- ✓ HUMAN-03: Agent detects agreement and sends actionable Slack alert — v1.0
- ✓ HUMAN-04: Agent supports human takeover of any thread — v1.0
- ✓ DATA-01: Agent accepts campaign data from ClickUp form submissions — v1.0
- ✓ DATA-02: Agent reads influencer outreach data from Google Sheet — v1.0
- ✓ DATA-03: Agent logs every sent/received email with timestamps, state, and rates — v1.0
- ✓ DATA-04: Agent maintains queryable audit trail by influencer, campaign, or date range — v1.0
- ✓ KB-01: Agent references knowledge base of influencer marketing best practices — v1.0
- ✓ KB-02: Agent references negotiation strategy guidelines when composing responses — v1.0
- ✓ KB-03: Knowledge base files are editable without code changes — v1.0

### Active

**Current Milestone: v1.1 Production Readiness**

**Goal:** Make the v1.0 negotiation agent production-grade — persistent state, reliable error handling, deployment infrastructure, CI/CD, monitoring, and live verification with real services.

**Target capabilities:**
- Persistent negotiation state that survives restarts/deploys
- Robust error handling, retries, and graceful degradation
- Docker-based deployment for cloud VM hosting
- GitHub Actions CI/CD with automated testing
- Structured logging, health checks, and monitoring
- Live verification with real Gmail, Sheets, and Slack

### Out of Scope

- Full outreach automation (cold email) — future agent handles this; team uses Instantly today
- Campaign-level CPM optimization across influencers — future "strategist" agent territory
- Web dashboard — v1 uses Slack notifications; dashboard deferred
- Contract generation/sending — legal liability; human sends contracts after agent alerts deal
- Direct platform API integration for pulling influencer metrics — metrics are pre-loaded
- Fully autonomous mode — v1 is hybrid with human escalation; trust must be earned
- DM/chat negotiation — email-first; platform DM APIs are restricted
- Multi-language support — negotiation nuance doesn't translate well; English-only for v1

## Context

- Team currently uses Instantly for cold email outreach, then manually handles negotiation replies
- Influencer metrics (avg views from 9 recent posts) are pre-loaded into campaign data, not pulled live
- Campaign information is input via ClickUp forms with key details per client project
- CPM pricing model: start negotiations at $20 CPM, willing to move up toward $30 CPM per influencer
- $30 CPM is the per-influencer escalation threshold; future agent will manage campaign-level CPM averaging
- This is the first agent in a planned team of collaborative agents covering the full influencer marketing pipeline
- v1.0 shipped with 691 tests, 22/22 requirements satisfied, all E2E flows verified

## Constraints

- **Email integration**: Gmail API with Pub/Sub push notifications for reliable send/receive with threading
- **Slack integration**: Slack Bolt with Block Kit formatting for actionable alerts
- **Data input**: ClickUp webhook endpoint for structured campaign data ingestion
- **Negotiation logic**: CPM calculation excludes viral outlier posts; deterministic pricing engine (no LLM in pricing)
- **Hybrid mode**: Every email the agent sends is reviewable; escalation includes full context
- **Audit trail**: SQLite-backed, queryable via CLI and Slack /audit command

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid mode for v1 | Build trust before full autonomy; reduce risk of bad negotiations | ✓ Good — escalation system works well |
| Slack for escalation + alerts (no dashboard) | Keep v1 simple; dashboard is future scope | ✓ Good — Block Kit alerts are actionable |
| Pre-loaded metrics (no live API pulls) | Simpler architecture; metrics already available from existing workflow | ✓ Good — decouples from external APIs |
| Gmail API for email | Reliable send/receive with threading and Pub/Sub push notifications | ✓ Good — MIME parsing handles edge cases |
| CPM-based pricing ($20-$30 range) | Matches team's existing negotiation strategy | ✓ Good — deterministic engine is predictable |
| Anthropic SDK for LLM | Intent classification + email composition; structured outputs for reliability | ✓ Good — validation gate catches LLM errors |
| SQLite for audit trail | Simple, zero-config, sufficient for v1 query patterns | ✓ Good — CLI + Slack query interface works |
| In-memory negotiation state | v1 limitation; persistent backend swappable without interface change | ⚠️ Revisit — lost on restart |
| Knowledge base as flat files | Team can edit without code changes (KB-03 requirement) | ✓ Good — stored at project root |
| Deterministic validation gate | No LLM validates LLM output; regex + string matching only | ✓ Good — catches dollar amount errors reliably |

---
*Last updated: 2026-02-19 after v1.1 milestone start*
