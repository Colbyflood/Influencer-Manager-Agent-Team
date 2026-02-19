# Phase 5: Campaign Ingestion and Operational Readiness - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Campaign data flows in automatically from ClickUp via webhook, every negotiation action is logged with a queryable audit trail (SQLite), and the system is production-ready with error handling and retry logic. This phase connects the existing negotiation pipeline (Phases 1-4) to external campaign data and adds operational visibility.

Out of scope: Cold outreach automation, new negotiation strategies, UI dashboards.

</domain>

<decisions>
## Implementation Decisions

### ClickUp Campaign Ingestion
- ClickUp webhook integration (real-time, not polling)
- Standard field set: client name, budget, target deliverables, influencer list, CPM range, platform, timeline
- One campaign can cover many influencers — a single submission lists multiple influencers, agent starts negotiations with all of them
- Auto-start negotiations on webhook receipt — agent immediately begins outreach, team gets a Slack notification that it started
- One-way data flow only: ClickUp -> agent (no status sync back to ClickUp)

### Conversation Audit Trail
- SQLite database for storage — queryable with SQL, zero infrastructure, easy to back up
- Full context per entry: timestamp, direction (sent/received), email body, negotiation state, rates used, intent classification, campaign ID, influencer name
- Log everything: emails, escalations, takeovers, campaign starts, state transitions, agreement closures
- Both CLI and Slack query interfaces: CLI for detailed queries (by influencer, campaign, date range), Slack commands for quick lookups

### Campaign-to-Negotiation Mapping
- Campaign-level CPM target range applies to all influencers as default
- Dynamic adjustment: agent tracks running campaign average CPM and adjusts flexibility for remaining influencers to hit overall target
- Flexibility considers engagement quality — not just raw CPM. Agent factors in follower engagement rate to determine if going past target CPM provides benefit by reaching a highly engaged audience. The agent should not decide on campaign CPM averaging alone
- Missing influencers (not in Google Sheet): skip and post Slack alert asking team to add them first

### Production Hardening
- Retry then escalate on API failures: retry 3 times with backoff, then post error to Slack #errors channel for team visibility
- Applies to all external APIs: Gmail, Slack, ClickUp, Anthropic

### Claude's Discretion
- Runtime model (long-running process vs event-driven)
- Config management approach (env vars, config files, or hybrid)
- Logging format (structured JSON vs console)
- Exact retry backoff strategy and timing
- SQLite schema design
- Slack audit query response formatting

</decisions>

<specifics>
## Specific Ideas

- Campaign average CPM tracking should consider engagement quality metrics alongside raw CPM — a highly engaged influencer at slightly above-target CPM may be worth more than a low-engagement influencer under target
- The agent should not make CPM flexibility decisions based on campaign averaging alone

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-campaign-ingestion-and-operational-readiness*
*Context gathered: 2026-02-19*
