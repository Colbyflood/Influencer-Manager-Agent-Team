# Requirements: Influencer Negotiation Agent

**Defined:** 2026-03-09
**Core Value:** The agent must negotiate influencer rates accurately using CPM-based logic and reliably communicate the outcome -- every agreed deal must result in a clear, actionable Slack notification to the team.

## v1.4 Requirements

Requirements for Per-Campaign Influencer Sheets milestone. Each maps to roadmap phases.

### Sheet Configuration

- [x] **SHEET-01**: Agent supports per-campaign worksheet tab name specified via ClickUp form field
- [x] **SHEET-02**: Agent supports optional per-campaign spreadsheet ID override (separate sheet instead of tab in master sheet)
- [x] **SHEET-03**: Agent defaults to master spreadsheet (GOOGLE_SHEETS_KEY) when no override is provided

### Ingestion

- [x] **INGEST-01**: Campaign model includes `influencer_sheet_tab` field parsed from ClickUp form
- [x] **INGEST-02**: Campaign model includes optional `influencer_sheet_id` field for spreadsheet override
- [x] **INGEST-03**: Ingestion pipeline passes per-campaign tab/sheet to `find_influencer()` instead of hardcoded "Sheet1"

### Sheet Monitoring

- [ ] **MON-01**: Agent polls each active campaign's sheet tab hourly to detect new influencer rows
- [ ] **MON-02**: Agent auto-starts negotiations for newly discovered influencers (rows added after initial ingestion)
- [ ] **MON-03**: Agent sends Slack alert when an existing influencer's row is modified after negotiation has started
- [ ] **MON-04**: Agent tracks which influencer rows have been processed to avoid duplicate outreach

## Future Requirements

### Sheet Monitoring Enhancements

- **MON-05**: Agent supports webhook-based sheet change detection (Google Sheets API push notifications) instead of polling
- **MON-06**: Dashboard shows per-campaign influencer sheet status (last polled, new rows found, pending outreach)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Creating/managing Google Sheets from the agent | Sheets are created by the team during campaign planning |
| Syncing influencer data back to the sheet | Agent reads from sheet, doesn't write to it |
| Multi-sheet per campaign (e.g., separate tabs for different platforms) | One tab per campaign is sufficient; platform is a column |
| Real-time sheet change detection | Hourly polling is sufficient; Google Sheets push API adds complexity |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SHEET-01 | Phase 22 | Complete |
| SHEET-02 | Phase 22 | Complete |
| SHEET-03 | Phase 22 | Complete |
| INGEST-01 | Phase 22 | Complete |
| INGEST-02 | Phase 22 | Complete |
| INGEST-03 | Phase 22 | Complete |
| MON-01 | Phase 23 | Pending |
| MON-02 | Phase 23 | Pending |
| MON-03 | Phase 23 | Pending |
| MON-04 | Phase 23 | Pending |

**Coverage:**
- v1.4 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
