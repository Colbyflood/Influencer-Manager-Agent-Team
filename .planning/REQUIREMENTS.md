# Requirements: Influencer Negotiation Agent

**Defined:** 2026-03-08
**Core Value:** The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome -- every agreed deal must result in a clear, actionable Slack notification to the team.

## v1.2 Requirements

Requirements for v1.2 Real-World Negotiation Intelligence. Each maps to roadmap phases.

### Campaign Data

- [x] **CAMP-01**: Agent ingests all 42 ClickUp form fields including background, goals, deliverables, budget, and campaign requirements sections
- [x] **CAMP-02**: Agent parses campaign goals (primary/secondary goal, business context, optimize-for strategy) and uses them to anchor negotiation approach
- [x] **CAMP-03**: Agent parses deliverable scenarios (3 tiers of minimum deliverables) and uses them as negotiation fallback positions
- [x] **CAMP-04**: Agent parses usage rights targets and minimums (paid usage, whitelisting, organic/owned) with duration tiers from 30 days to perpetual
- [x] **CAMP-05**: Agent parses budget constraints including per-influencer min cost floor, max cost without human approval, and campaign budget
- [x] **CAMP-06**: Agent parses product leverage fields (product available, description, monetary value) for use as negotiation incentive
- [x] **CAMP-07**: Agent parses campaign requirements (exclusivity terms, content approval, revision rounds, raw footage, delivery/publish dates)
- [x] **CAMP-08**: Agent uses CPM Target and CPM Leniency percentage instead of fixed $20-$30 CPM range

### Negotiation Logic

- [x] **NEG-08**: Agent opens with more deliverables and lower rate than budget allows, creating room to concede during negotiation
- [x] **NEG-09**: Agent trades deliverable tiers downward (scenario 1 -> 2 -> 3) when influencer rate exceeds budget, preserving core content
- [x] **NEG-10**: Agent negotiates usage rights duration downward (target -> minimum) as a cost-reduction lever
- [x] **NEG-11**: Agent offers product/upgrade as additional value when cash rate is at ceiling but influencer hasn't accepted
- [x] **NEG-12**: Agent enforces per-influencer cost floor (never offers below minimum) and escalates to human when rate exceeds max without approval
- [x] **NEG-13**: Agent can selectively share CPM target with motivated influencers to justify budget constraints
- [x] **NEG-14**: Agent proposes content syndication (cross-posting IG to TikTok) as added value rather than unique deliverables per platform
- [x] **NEG-15**: Agent initiates polite exit when deal economics don't work, preserving relationship for future campaigns

### Counterparty Intelligence

- [x] **CPI-01**: Agent detects whether email counterparty is an influencer or talent manager/agency based on email signatures, domain, and thread context
- [ ] **CPI-02**: Agent tracks agency name and multiple contacts per negotiation thread (e.g. manager + assistant)
- [ ] **CPI-03**: Agent adjusts negotiation tone for talent managers (more transactional, data-backed arguments) vs direct influencers (more relationship-driven, creative alignment)
- [ ] **CPI-04**: Agent handles multi-person threads where manager loops in assistant or influencer without losing negotiation context

### Knowledge Base

- [x] **KB-04**: Knowledge base includes negotiation playbook with standards, levers, and budget maximization strategy from AGM docs
- [x] **KB-05**: Knowledge base includes real email examples covering positive close, escalation, walk-away, bundled rate, CPM mention, and misalignment exit scenarios
- [x] **KB-06**: Agent selects relevant email examples as style reference when composing responses based on current negotiation stage and scenario

### Email Composition

- [ ] **EMAIL-05**: Agent composes emails with professional but warm tone matching AGM style (partnership-first, acknowledge creator value, concise)
- [ ] **EMAIL-06**: Agent formats counter-offers with clear SOW structure (deliverable list, usage terms, rate with strikethrough adjustments) matching real email format
- [ ] **EMAIL-07**: Agent includes payment terms and next steps in agreement confirmation emails

## Future Requirements

### Campaign Strategy

- **STRAT-01**: Agent optimizes campaign-level CPM across influencer portfolio (budget averaging)
- **STRAT-02**: Agent evaluates influencer worth beyond CPM based on brand fit and content style

### Outreach

- **OUT-01**: Agent handles cold outreach to gauge interest before discussing rates

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full outreach automation (cold email) | Future agent handles this; team uses Instantly today |
| Campaign-level CPM optimization | Future "strategist" agent territory |
| Web dashboard | Slack notifications sufficient for current scale |
| Contract generation/sending | Legal liability; human sends contracts after agent alerts deal |
| Live platform API metrics | Metrics are pre-loaded from existing workflow |
| Phone call handling | Agent noted in email examples that managers request calls; agent stays email-only, escalates call requests to human |
| Influencer list from form | Influencers come from separate Google Sheet source, not the ClickUp form |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAMP-01 | Phase 13 | Complete |
| CAMP-02 | Phase 13 | Complete |
| CAMP-03 | Phase 13 | Complete |
| CAMP-04 | Phase 13 | Complete |
| CAMP-05 | Phase 13 | Complete |
| CAMP-06 | Phase 13 | Complete |
| CAMP-07 | Phase 13 | Complete |
| CAMP-08 | Phase 13 | Complete |
| NEG-08 | Phase 15 | Complete |
| NEG-09 | Phase 15 | Complete |
| NEG-10 | Phase 15 | Complete |
| NEG-11 | Phase 15 | Complete |
| NEG-12 | Phase 15 | Complete |
| NEG-13 | Phase 15 | Complete |
| NEG-14 | Phase 15 | Complete |
| NEG-15 | Phase 15 | Complete |
| CPI-01 | Phase 16 | Complete |
| CPI-02 | Phase 16 | Pending |
| CPI-03 | Phase 16 | Pending |
| CPI-04 | Phase 16 | Pending |
| KB-04 | Phase 14 | Complete |
| KB-05 | Phase 14 | Complete |
| KB-06 | Phase 14 | Complete |
| EMAIL-05 | Phase 17 | Pending |
| EMAIL-06 | Phase 17 | Pending |
| EMAIL-07 | Phase 17 | Pending |

**Coverage:**
- v1.2 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after roadmap creation*
