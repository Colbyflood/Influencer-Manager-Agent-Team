# Phase 3: LLM Negotiation Pipeline - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The agent can understand influencer email replies (extract intent, rate proposals, deliverable changes), compose intelligent counter-offers guided by a knowledge base, and execute the core negotiation loop end-to-end. This phase wires up the LLM to the pricing engine and email system built in Phases 1-2.

Out of scope: Slack escalation UI (Phase 4), campaign data ingestion (Phase 5), cold outreach.

</domain>

<decisions>
## Implementation Decisions

### Email Composition & Tone
- Professional but warm tone — like a talent manager who's done this 1000 times
- Tone adaptation by negotiation stage: Claude's discretion on how to shift between initial offer, counters, and final offers
- Email content is flexible by context — include rationale (e.g., "based on your reach") when countering down, skip it when rate is close to agreement
- No signature block needed on emails

### Knowledge Base Structure
- Format: Claude's discretion (pick what works best for LLM consumption and non-technical editing)
- Content: Negotiation tactics, tone rules, AND example emails as style references
- Per-platform sections — different guidance for Instagram, TikTok, YouTube (different creator norms per platform)
- Editors are non-technical team members (marketing/talent managers) — editing experience must be simple, no code knowledge assumed

### Validation & Safety Gates
- Full validation suite before any email is sent: rate within CPM bounds, deliverable accuracy, no hallucinated commitments, no off-brand language, monetary values match calculations
- On validation failure: escalate to human immediately (don't send the email, route to Slack escalation with draft + failure reason)
- Intent classification uses confidence threshold — escalate to human on low confidence rather than guessing wrong
- Configurable max autonomous rounds (default cap, team can change per campaign or globally) — escalate after cap reached without agreement

### Claude's Discretion
- Tone shift strategy between negotiation stages
- Knowledge base file format (markdown, YAML, etc.)
- Loading skeleton and error state designs
- Intent classification confidence threshold value
- Default max round cap number

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-llm-negotiation-pipeline*
*Context gathered: 2026-02-18*
