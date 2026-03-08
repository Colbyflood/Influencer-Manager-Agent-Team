---
phase: 17-email-composition-and-style
plan: 01
subsystem: llm
tags: [sow, strikethrough, email-composition, agm-style, prompts]

# Dependency graph
requires:
  - phase: 15-lever-driven-composition
    provides: "compose_counter_email with lever_instructions parameter"
  - phase: 16-counterparty-intelligence
    provides: "counterparty_context parameter for tone adjustment"
provides:
  - "SOW formatter with strikethrough rate adjustments (format_sow_block, format_rate_adjustment)"
  - "AGM partnership style enforcement in system prompt"
  - "SOW block injection into composer user prompt"
affects: [17-02, email-composition, negotiation-loop]

# Tech tracking
tech-stack:
  added: []
  patterns: ["deterministic SOW block generation separate from LLM composition", "strikethrough rate formatting for counter-offers"]

key-files:
  created:
    - src/negotiation/llm/sow_formatter.py
    - tests/llm/test_sow_formatter.py
  modified:
    - src/negotiation/llm/prompts.py
    - src/negotiation/llm/composer.py
    - tests/llm/test_composer.py

key-decisions:
  - "Non-numeric rate values handled gracefully (return as-is) for backward compatibility with 'not specified' rates"
  - "SOW block built deterministically outside LLM and injected as-is into prompt to prevent reformulation"

patterns-established:
  - "Deterministic formatting: structured blocks (SOW, rates) built in Python and embedded verbatim in LLM prompts"
  - "Currency formatting with _format_currency handles $, commas, and non-numeric gracefully"

requirements-completed: [EMAIL-05, EMAIL-06]

# Metrics
duration: 12min
completed: 2026-03-08
---

# Phase 17 Plan 01: AGM Style & SOW Formatter Summary

**Deterministic SOW block builder with strikethrough rate adjustments and AGM partnership style enforcement in email prompts**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-08T23:15:20Z
- **Completed:** 2026-03-08T23:27:20Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created sow_formatter.py with format_rate_adjustment (strikethrough) and format_sow_block (structured deliverable/usage/rate blocks)
- Updated EMAIL_COMPOSITION_SYSTEM_PROMPT with AGM partnership style rules and SOW embedding instruction
- Wired SOW formatter into compose_counter_email with full backward compatibility
- All 84 LLM tests pass (10 new SOW formatter + 4 new composer + 70 existing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SOW formatter and update prompts for AGM style** - `6747b53` (feat)
2. **Task 2: Wire SOW formatter into composer and update existing tests** - `291c34b` (feat)

## Files Created/Modified
- `src/negotiation/llm/sow_formatter.py` - Deterministic SOW block builder with strikethrough rate formatting
- `src/negotiation/llm/prompts.py` - AGM style enforcement and {sow_block} placeholder in user prompt
- `src/negotiation/llm/composer.py` - SOW block generation and injection into LLM prompt
- `tests/llm/test_sow_formatter.py` - 10 tests for rate formatting and SOW block generation
- `tests/llm/test_composer.py` - 4 new tests for SOW integration in composer

## Decisions Made
- Non-numeric rate values (e.g., "not specified") handled gracefully by returning as-is instead of raising ValueError -- required for backward compatibility with existing negotiation loop test
- SOW block built deterministically in Python and embedded verbatim in prompt to prevent LLM reformulation of rate values or structure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _format_currency crash on non-numeric rate values**
- **Found during:** Task 2 (wiring SOW formatter into composer)
- **Issue:** Existing test_question_intent_composes_response passes "not specified" as their_rate, which caused ValueError in _format_currency
- **Fix:** Added try/except in _format_currency to return non-numeric values as-is
- **Files modified:** src/negotiation/llm/sow_formatter.py
- **Verification:** All 84 tests pass including the previously failing test
- **Committed in:** 291c34b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential for backward compatibility. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SOW formatter and AGM style prompts ready for Plan 02 (email template library or further composition refinements)
- format_sow_block and format_rate_adjustment exported and importable by any module

## Self-Check: PASSED

All 5 created/modified files verified on disk. Both task commits (6747b53, 291c34b) verified in git log.

---
*Phase: 17-email-composition-and-style*
*Completed: 2026-03-08*
