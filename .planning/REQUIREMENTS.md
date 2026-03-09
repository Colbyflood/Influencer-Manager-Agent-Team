# Requirements: Influencer Negotiation Agent

**Defined:** 2026-03-08
**Core Value:** The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome -- every agreed deal must result in a clear, actionable Slack notification to the team.

## v1.3 Requirements

Requirements for v1.3 Campaign Dashboard. Each maps to roadmap phases.

### Dashboard Views

- [x] **VIEW-01**: User can view a campaign list showing all campaigns with status summary (active negotiations, agreed, escalated, total influencers)
- [ ] **VIEW-02**: User can view campaign detail page showing every influencer and their current negotiation state, rate, round count, and counterparty type
- [ ] **VIEW-03**: User can view per-influencer negotiation timeline showing state transitions, emails exchanged, and rate history
- [x] **VIEW-04**: User can see campaign-level metrics: average CPM achieved, percentage closed, budget utilization

### Controls

- [ ] **CTRL-01**: User can pause/stop negotiation with a specific influencer from the dashboard
- [ ] **CTRL-02**: User can resume a paused negotiation from the dashboard
- [ ] **CTRL-03**: User can stop all negotiations associated with a specific talent agent or agency

### API

- [x] **API-01**: Backend exposes campaign list endpoint with per-campaign status aggregation
- [ ] **API-02**: Backend exposes campaign detail endpoint with per-influencer negotiation data
- [ ] **API-03**: Backend exposes negotiation control endpoints (pause, resume, stop)
- [ ] **API-04**: Backend exposes per-influencer timeline endpoint with state transitions and email history

### Frontend Infrastructure

- [x] **UI-01**: React + Tailwind CSS frontend application with campaign list and detail views
- [x] **UI-02**: Dashboard served alongside existing FastAPI backend (static files or dev proxy)
- [x] **UI-03**: Dashboard updates via polling (configurable interval) for near-real-time status

## Future Requirements

### Dashboard Enhancements

- **VIEW-05**: User can view email content inline in the negotiation timeline
- **CTRL-04**: Dashboard actions post notifications to Slack
- **AUTH-01**: Multi-user authentication with role-based access

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user auth | Single-user dashboard sufficient for current team size; defer to future |
| WebSocket real-time updates | Polling sufficient for dashboard refresh; WebSocket adds complexity |
| Mobile-responsive design | Desktop-first; team uses dashboard on workstations |
| Email composition from dashboard | Agent composes emails; dashboard is monitoring and control only |
| Campaign creation from dashboard | Campaigns come from ClickUp forms; dashboard is read + control |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| VIEW-01 | Phase 19 | Complete |
| VIEW-02 | Phase 20 | Pending |
| VIEW-03 | Phase 20 | Pending |
| VIEW-04 | Phase 19 | Complete |
| CTRL-01 | Phase 21 | Pending |
| CTRL-02 | Phase 21 | Pending |
| CTRL-03 | Phase 21 | Pending |
| API-01 | Phase 19 | Complete |
| API-02 | Phase 20 | Pending |
| API-03 | Phase 21 | Pending |
| API-04 | Phase 20 | Pending |
| UI-01 | Phase 18 | Complete |
| UI-02 | Phase 18 | Complete |
| UI-03 | Phase 19 | Complete |

**Coverage:**
- v1.3 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after roadmap creation*
