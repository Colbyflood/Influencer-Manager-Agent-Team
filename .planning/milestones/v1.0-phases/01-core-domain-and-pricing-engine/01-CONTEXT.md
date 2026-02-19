# Phase 1: Core Domain and Pricing Engine - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Deterministic pricing logic, negotiation state machine, platform-specific rate cards, and rate boundary enforcement. Pure business rules with zero external dependencies — no email, no Slack, no Google Sheets. This phase produces tested, standalone modules that all downstream phases depend on.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User opted to skip detailed discussion — the roadmap provides clear direction. Claude has full flexibility on implementation decisions within this phase, guided by:

- **CPM rate calculation**: Agent reads pre-calculated pay ranges from Google Sheets (Phase 2), but the pricing engine in this phase should accept pay range inputs and calculate rates per deliverable type within the $20-$30 CPM range
- **Negotiation state machine**: States defined in requirements (initial_offer, awaiting_reply, counter_received, counter_sent, agreed, rejected, escalated, stale) with invalid transitions rejected
- **Platform rate cards**: Support Instagram (post, story, reel), TikTok (video, story), YouTube (dedicated video, integration, short) with platform-aware pricing
- **Rate boundary enforcement**: Escalate when CPM exceeds $30 threshold; flag unusually low rates (possible misunderstanding)

</decisions>

<specifics>
## Specific Ideas

- CPM range is $20-$30 — start offers at $20 CPM floor, negotiate up toward $30 CPM ceiling
- The $30 CPM is a per-influencer escalation threshold for v1; a future "strategist" agent will manage campaign-level CPM averaging
- Viral outlier detection is handled by a separate agent — this agent works with pre-calculated pay ranges
- All pricing math must be deterministic code, never LLM-generated (from research pitfalls)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-core-domain-and-pricing-engine*
*Context gathered: 2026-02-18*
