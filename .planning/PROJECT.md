# Influencer Negotiation Agent

## What This Is

An AI-powered agent that handles influencer rate negotiations via email on behalf of marketing teams. The agent picks up email threads where influencers have already responded to outreach, negotiates deliverable rates using CPM-based pricing logic, and alerts the team via Slack when agreements are reached. It operates in hybrid mode — autonomously handling routine negotiation while escalating edge cases to humans.

## Core Value

The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome — every agreed deal must result in a clear, actionable Slack notification to the team.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Receive and process influencer email replies from existing outreach threads
- [ ] Calculate target rate using pre-loaded metrics (avg views from 9 most recent posts, excluding viral outliers) at $20-$30 CPM range
- [ ] Compose and send negotiation emails that propose/counter rates based on CPM calculations
- [ ] Handle multi-platform negotiations (Instagram, TikTok, YouTube, and others)
- [ ] Support all deliverable types: social posts, stories/ephemeral, long-form video, usage rights
- [ ] Autonomously handle routine negotiation back-and-forth (hybrid mode)
- [ ] Escalate edge cases to human via Slack with context and suggested response
- [ ] Escalate when influencer rate exceeds $30 CPM threshold
- [ ] Send actionable Slack alert on agreement (influencer name, agreed rate, deliverables, platform, next steps)
- [ ] Accept campaign data input (client info, budget, target deliverables, influencer metrics, CPM range)

### Out of Scope

- Full outreach automation (cold email) — future agent handles this
- Campaign-level CPM optimization across influencers — future "strategist" agent
- Web dashboard — v1 uses Slack notifications, dashboard deferred
- Contract generation/sending — downstream from negotiation
- Direct platform API integration for pulling influencer metrics — metrics are pre-loaded
- Fully autonomous mode — v1 is hybrid with human escalation

## Context

- Team currently uses Instantly for cold email outreach, then manually handles negotiation replies
- Influencer metrics (avg views from 9 recent posts) are pre-loaded into campaign data, not pulled live
- Campaign information will be input via ClickUp forms with key details per client project
- CPM pricing model: start negotiations at $20 CPM, willing to move up toward $30 CPM per influencer
- $30 CPM is the per-influencer escalation threshold for v1; future agent will manage campaign-level CPM averaging
- This is the first agent in a planned team of collaborative agents covering the full influencer marketing pipeline
- Email integration is flexible — Gmail API is the likely path but open to alternatives

## Constraints

- **Email integration**: Must support reliable send/receive with threading — Gmail API is primary candidate
- **Slack integration**: Must support rich message formatting for actionable alerts
- **Data input**: Must accept structured campaign data (likely from ClickUp form/webhook)
- **Negotiation logic**: CPM calculation must exclude viral outlier posts from average views
- **Hybrid mode**: Every email the agent sends must be reviewable; escalation must include full context

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid mode for v1 | Build trust before full autonomy; reduce risk of bad negotiations | — Pending |
| Slack for escalation + alerts (no dashboard) | Keep v1 simple; dashboard is future scope | — Pending |
| Pre-loaded metrics (no live API pulls) | Simpler architecture; metrics already available from existing workflow | — Pending |
| Flexible email provider | Gmail API likely but don't lock in yet; may need to support Instantly | — Pending |
| CPM-based pricing ($20-$30 range) | Matches team's existing negotiation strategy | — Pending |

---
*Last updated: 2026-02-18 after initialization*
