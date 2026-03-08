---
phase: 16-counterparty-intelligence
plan: 01
subsystem: negotiation
tags: [email-classification, counterparty-detection, pydantic, regex, enum]

requires:
  - phase: 06-email-integration
    provides: InboundEmail model with from_email and body_text fields
provides:
  - CounterpartyType enum (DIRECT_INFLUENCER, TALENT_MANAGER)
  - DetectionSignal model for classification evidence
  - CounterpartyProfile model with confidence scoring
  - classify_counterparty function for email sender analysis
affects: [16-counterparty-intelligence, negotiation-pipeline]

tech-stack:
  added: []
  patterns: [signal-based-classification, confidence-scoring, domain-lookup-tables]

key-files:
  created:
    - src/negotiation/counterparty/__init__.py
    - src/negotiation/counterparty/models.py
    - src/negotiation/counterparty/classifier.py
    - tests/counterparty/__init__.py
    - tests/counterparty/test_models.py
    - tests/counterparty/test_classifier.py
  modified: []

key-decisions:
  - "Signal-based classification with strength weighting (0.0-1.0) for composable detection"
  - "13 known agency domains and 11 personal domains in lookup tables"
  - "Confidence thresholds: 0.9 for 2+ signals, 0.8 for strong signal, 0.6 for weak signal, 0.5 default"
  - "Signature scanning limited to last 10 lines of email body for performance"

patterns-established:
  - "Signal accumulation pattern: collect independent signals then aggregate for final classification"
  - "Frozen Pydantic models for immutable detection results"

requirements-completed: [CPI-01]

duration: 2min
completed: 2026-03-08
---

# Phase 16 Plan 01: Counterparty Detection Classifier Summary

**Signal-based email counterparty classifier detecting talent managers vs direct influencers via domain analysis, signature keyword scanning, and email structure assessment**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-08T22:16:55Z
- **Completed:** 2026-03-08T22:19:08Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 6

## Accomplishments
- CounterpartyType enum, DetectionSignal, and CounterpartyProfile frozen Pydantic models
- classify_counterparty function with 3-layer signal detection (domain, signature, structure)
- 13 known agency domain mappings with agency name extraction
- 26 tests covering agency domains, personal domains, custom domains, signature keywords, email structure, confidence scoring, and agency name extraction

## Task Commits

Each task was committed atomically:

1. **TDD RED: Models + failing tests** - `e0cd0df` (test)
2. **TDD GREEN: Classifier implementation** - `9acfd93` (feat)

## Files Created/Modified
- `src/negotiation/counterparty/__init__.py` - Package exports for CounterpartyType, DetectionSignal, CounterpartyProfile
- `src/negotiation/counterparty/models.py` - Frozen Pydantic models for classification results
- `src/negotiation/counterparty/classifier.py` - classify_counterparty with domain/signature/structure analysis
- `tests/counterparty/__init__.py` - Test package init
- `tests/counterparty/test_models.py` - 7 tests for model creation, enum values, frozen validation
- `tests/counterparty/test_classifier.py` - 19 tests for classifier covering all detection scenarios

## Decisions Made
- Signal-based classification with strength weighting for composable detection logic
- 13 known agency domains (UTA, WME, CAA, ICM, Paradigm, Gersh, APA, etc.) with human-readable names
- Signature scanning limited to last 10 lines to focus on sign-off block
- Confidence thresholds follow spec: 0.9 (2+ signals), 0.8 (strong signal), 0.6 (weak), 0.5 (default)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Classifier ready for integration with email processing pipeline
- CounterpartyProfile can be attached to InboundEmail processing flow
- Models ready for use by 16-02 and 16-03 plans

---
*Phase: 16-counterparty-intelligence*
*Completed: 2026-03-08*
