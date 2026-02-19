# Phase 4: Slack and Human-in-the-Loop - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The team receives actionable Slack notifications for escalations and agreements, and can take over any negotiation thread at any time. This phase connects Phase 3's EscalationPayload and agreement detection to Slack, adds configurable escalation trigger rules, and implements human takeover (both via email reply and Slack command).

Out of scope: Campaign data ingestion (Phase 5), audit trail logging (Phase 5), cold outreach.

</domain>

<decisions>
## Implementation Decisions

### Escalation Message Format
- Summary format with link to full details — not everything inline
- Always include: influencer name, influencer email address, client name, escalation reason, key numbers (proposed vs target rate)
- Include suggested specific actions (e.g., "Reply with counter at $X" or "Approve this rate")
- No urgency indicators (no time-since-reply, no round count)
- Single dedicated Slack channel for all escalations
- Specific reason with evidence — name the exact trigger and quote relevant text from the email

### Agreement Alert Content
- Deal summary + next steps (e.g., "Send contract", "Confirm deliverables")
- Always include: influencer name, influencer email address, client name, agreed rate, platform, deliverables, CPM achieved
- Separate dedicated Slack channel for agreements (not same as escalations)
- Configurable per-campaign tagging — campaign data specifies who to @ mention

### Human Takeover Flow
- Support both methods: detect human email reply in thread AND Slack command to claim thread
- Silent handoff — no Slack notification when human takes over, agent just stops
- Re-enable via Slack command (e.g., '/resume @influencer') — human can hand thread back to agent
- Human detection method: Claude's discretion (based on Gmail API capabilities from Phase 2)

### Escalation Trigger Rules
- All triggers active by default: CPM over threshold, ambiguous intent, hostile tone, legal/contract language, unusual deliverable requests
- Team can disable specific triggers if too noisy
- Triggers defined in a config file (YAML/JSON) that team can edit without code changes — add keywords, change thresholds
- Tone-based triggers (hostile tone, legal language) use LLM-based detection, not keyword matching
- Escalation reason is specific with evidence — quote the triggering text

### Claude's Discretion
- Human reply detection method in email threads
- Config file format for escalation triggers (YAML vs JSON)
- Slack message formatting and Block Kit structure
- Link format for "full details" in escalation messages

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

*Phase: 04-slack-and-human-in-the-loop*
*Context gathered: 2026-02-18*
