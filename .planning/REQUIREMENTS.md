# Requirements: Influencer Negotiation Agent

**Defined:** 2026-02-18
**Core Value:** The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome — every agreed deal must result in a clear, actionable Slack notification to the team.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Email Integration

- [x] **EMAIL-01**: Agent can send emails via Gmail API on behalf of the team
- [x] **EMAIL-02**: Agent can receive and process inbound emails via Gmail API with push notifications
- [x] **EMAIL-03**: Agent maintains email thread context so influencers see a coherent conversation history
- [x] **EMAIL-04**: Agent can parse influencer reply content from email threads (handle MIME, inline replies, forwarding)

### Negotiation Logic

- [x] **NEG-01**: Agent reads influencer data from a Google Sheet, locates the row for the influencer being negotiated with, and pulls the proposed pay range based on $20-$30 CPM
- [x] **NEG-02**: Agent uses the pre-calculated pay range from the Google Sheet to guide negotiation (starting at $20 CPM floor, moving toward $30 CPM ceiling)
- [x] **NEG-03**: Agent supports platform-specific deliverable pricing for Instagram (post, story, reel), TikTok (video, story), and YouTube (dedicated video, integration, short)
- [x] **NEG-04**: Agent tracks negotiation state across multi-turn email conversations (states: initial_offer, awaiting_reply, counter_received, counter_sent, agreed, rejected, escalated, stale)
- [ ] **NEG-05**: Agent extracts rate proposals and deliverable changes from free-text influencer email replies using LLM
- [x] **NEG-06**: Agent composes counter-offer emails with calculated rates and clear deliverable terms
- [x] **NEG-07**: Agent enforces rate boundaries — escalates when influencer demands exceed $30 CPM threshold

### Human Integration

- [ ] **HUMAN-01**: Agent escalates edge cases to designated Slack channel with full context (conversation history, influencer metrics, proposed vs target rate, reason for escalation)
- [ ] **HUMAN-02**: Agent escalates based on configurable trigger rules (CPM over threshold, ambiguous intent, hostile tone, legal/contract language, unusual deliverable requests)
- [ ] **HUMAN-03**: Agent detects agreement in influencer replies and sends actionable Slack alert (influencer name, agreed rate, platform, deliverables, CPM achieved, next steps)
- [ ] **HUMAN-04**: Agent supports human takeover — when a human responds in a thread, agent stops autonomous handling of that thread

### Data & Operations

- [ ] **DATA-01**: Agent accepts campaign data from ClickUp form submissions to understand the specific deliverables, goals, channels needed, and other key details to guide decision making for negotiations
- [x] **DATA-02**: Agent connects to a Google Sheet to read influencer outreach data (name, contact info, platform, metrics, pre-calculated pay range)
- [ ] **DATA-03**: Agent logs every sent/received email with timestamps, negotiation state, and rates used
- [ ] **DATA-04**: Agent maintains queryable conversation audit trail by influencer, campaign, or date range

### Knowledge Base

- [x] **KB-01**: Agent references a curated knowledge base of influencer marketing best practices during negotiations
- [x] **KB-02**: Agent references negotiation strategy guidelines (anchoring, concession patterns, tone) when composing responses
- [x] **KB-03**: Knowledge base files are editable by the team to update guidance without code changes

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Email Enhancements

- **EMAIL-05**: Email template system with personalization variables (influencer name, rate, deliverables, brand)
- **EMAIL-06**: Stale negotiation detection with automatic follow-up emails (configurable thresholds: 48h, 72h)

### Advanced Negotiation

- **NEG-08**: Intelligent counter-offer strategy using anchoring, concession patterns, and BATNA-aware logic
- **NEG-09**: Negotiation style adaptation based on influencer communication style (formal vs casual)
- **NEG-10**: Deliverable bundling and unbundling when negotiation stalls on single deliverable price
- **NEG-11**: Confidence scoring for agreement detection (distinguish "sounds good" from conditional interest)
- **NEG-12**: Negotiation playbook configuration per brand/client (max rounds, concession rate, priority)

### Analytics & Memory

- **DATA-05**: Rate memory across negotiations (remember previous rates per influencer)
- **DATA-06**: Negotiation analytics via Slack (avg CPM, acceptance rate, negotiation duration, win/loss)
- **DATA-07**: Campaign data input via manual JSON as fallback to ClickUp

## Out of Scope

| Feature | Reason |
|---------|--------|
| Fully autonomous mode (no human) | Trust must be earned; v1 is hybrid with human escalation |
| Cold email outreach | Future agent handles this; team uses Instantly today |
| Contract generation/sending | Legal liability; human sends contracts after agent alerts deal |
| CPM rate calculation | Handled by a separate agent; this agent reads pre-calculated pay ranges from Google Sheet |
| Live influencer metrics pulling | Metrics pre-loaded; doesn't change fast enough to justify API complexity |
| DM/chat negotiation | Email-first; platform DM APIs are restricted |
| Multi-language support | Negotiation nuance doesn't translate well; English-only for v1 |
| Campaign budget allocation | Future "strategist" agent territory |
| Sentiment analysis | Not in negotiation agent's domain |
| Web dashboard | v1 uses Slack notifications; dashboard deferred |
| Usage rights pricing calculator | Different pricing model; most v1 deals are organic content |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EMAIL-01 | Phase 2 | Complete |
| EMAIL-02 | Phase 2 | Complete |
| EMAIL-03 | Phase 2 | Complete |
| EMAIL-04 | Phase 2 | Complete |
| NEG-01 | Phase 2 | Complete |
| NEG-02 | Phase 1 | Complete |
| NEG-03 | Phase 1 | Complete |
| NEG-04 | Phase 1 | Complete |
| NEG-05 | Phase 3 | Pending |
| NEG-06 | Phase 3 | Complete |
| NEG-07 | Phase 1 | Complete |
| HUMAN-01 | Phase 4 | Pending |
| HUMAN-02 | Phase 4 | Pending |
| HUMAN-03 | Phase 4 | Pending |
| HUMAN-04 | Phase 4 | Pending |
| DATA-01 | Phase 5 | Pending |
| DATA-02 | Phase 2 | Complete |
| DATA-03 | Phase 5 | Pending |
| DATA-04 | Phase 5 | Pending |
| KB-01 | Phase 3 | Complete |
| KB-02 | Phase 3 | Complete |
| KB-03 | Phase 3 | Complete |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-19 after 03-01 plan completion*
