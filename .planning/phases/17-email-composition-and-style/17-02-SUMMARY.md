---
phase: 17-email-composition-and-style
plan: 02
subsystem: llm
tags: [agreement-email, payment-terms, next-steps, validation, negotiation-loop]

# Dependency graph
requires:
  - phase: 17-01
    provides: "SOW formatter with format_sow_block for structured term blocks"
  - phase: 16-counterparty-intelligence
    provides: "counterparty_context and get_tone_guidance for tone adjustment"
provides:
  - "compose_agreement_email function for deal confirmation with payment terms and next steps"
  - "AGREEMENT_CONFIRMATION prompts (system + user) enforcing term recap, payment terms, numbered next steps"
  - "Agreement-aware validation mode (is_agreement) that permits usage rights and warns on missing payment terms"
  - "Accept branch in negotiation loop now composes and returns agreement confirmation email"
affects: [email-composition, negotiation-loop, orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["agreement-aware validation mode with is_agreement flag", "accept branch email composition with graceful validation fallback"]

key-files:
  created:
    - tests/llm/test_agreement_composer.py
  modified:
    - src/negotiation/llm/prompts.py
    - src/negotiation/llm/composer.py
    - src/negotiation/llm/negotiation_loop.py
    - src/negotiation/llm/validation.py
    - tests/llm/test_validation.py
    - tests/llm/test_negotiation_loop.py

key-decisions:
  - "Agreement emails use format_sow_block with agreed rate directly (no strikethrough) for clean term presentation"
  - "Validation fallback on agreement: accept anyway but include validation_warnings for human review"
  - "Usage rights hallucination check skipped for agreement emails since they legitimately reference agreed usage terms"

patterns-established:
  - "Agreement-aware validation: is_agreement flag controls which hallucination patterns to skip and adds domain-specific checks"
  - "Accept branch graceful degradation: validation failure does not block acceptance, warnings passed for human review"

requirements-completed: [EMAIL-07]

# Metrics
duration: 8min
completed: 2026-03-08
---

# Phase 17 Plan 02: Agreement Confirmation Email Composer Summary

**Agreement email composer with payment terms, numbered next steps, and agreement-aware validation wired into negotiation loop accept path**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-08T23:36:32Z
- **Completed:** 2026-03-08T23:44:32Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Created compose_agreement_email function with dedicated AGREEMENT_CONFIRMATION prompts enforcing term recap, payment terms, and numbered next steps
- Wired agreement email composition into negotiation loop accept branch with knowledge base loading, counterparty tone, and validation
- Added is_agreement mode to validation gate: skips usage rights hallucination check, warns on missing payment terms
- All 96 LLM tests pass (12 new + 84 existing), 334 total relevant tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add agreement confirmation prompts and composer function** - `0455ec4` (feat)
2. **Task 2: Wire agreement composer into negotiation loop and update validation** - `3dd627f` (feat)

## Files Created/Modified
- `src/negotiation/llm/prompts.py` - Added AGREEMENT_CONFIRMATION_SYSTEM_PROMPT and AGREEMENT_CONFIRMATION_USER_PROMPT
- `src/negotiation/llm/composer.py` - Added compose_agreement_email function using SOW formatter for agreed terms
- `src/negotiation/llm/negotiation_loop.py` - Accept branch now composes agreement email with KB, tone, and validation
- `src/negotiation/llm/validation.py` - Added is_agreement mode: skips usage rights, warns on missing payment terms
- `tests/llm/test_agreement_composer.py` - 7 tests for agreement email composition
- `tests/llm/test_validation.py` - 3 new tests for agreement validation mode
- `tests/llm/test_negotiation_loop.py` - 2 new tests for accept branch email composition, 1 updated existing test

## Decisions Made
- Agreement emails use format_sow_block with agreed rate directly (no strikethrough) since both parties have agreed on the rate
- Validation failure on agreement email does not block acceptance -- warnings are passed through for human review rather than escalating
- Usage rights hallucination check skipped in agreement mode since agreement emails legitimately reference agreed usage terms

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test_accept_transitions_to_agreed mock configuration**
- **Found during:** Task 2 (wiring agreement composer into negotiation loop)
- **Issue:** Existing test did not configure mock_client.messages.create for the new agreement email composition call, causing MagicMock to be passed to Pydantic ComposedEmail
- **Fix:** Added compose_text parameter to _configure_mock_client call in the existing test
- **Files modified:** tests/llm/test_negotiation_loop.py
- **Verification:** All 14 negotiation loop tests pass
- **Committed in:** 3dd627f (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential update to existing test for new behavior. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Agreement email composition fully integrated into negotiation loop accept path
- Validation gate has agreement-aware mode ready for any future agreement-related email types
- compose_agreement_email exported and importable by orchestration layer

## Self-Check: PASSED

All 7 created/modified files verified on disk. Both task commits (0455ec4, 3dd627f) verified in git log.

---
*Phase: 17-email-composition-and-style*
*Completed: 2026-03-08*
