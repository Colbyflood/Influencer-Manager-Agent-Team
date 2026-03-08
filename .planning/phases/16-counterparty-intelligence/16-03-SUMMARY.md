---
phase: 16-counterparty-intelligence
plan: 03
subsystem: negotiation
tags: [tone-adjustment, llm-prompts, counterparty, negotiation-style]

# Dependency graph
requires:
  - phase: 16-01
    provides: "CounterpartyType enum and classifier that detects talent_manager vs direct_influencer"
provides:
  - "get_tone_guidance function returning counterparty-specific tone instructions"
  - "Composer counterparty_context parameter for tone injection into LLM prompts"
  - "Negotiation loop auto-generates tone guidance from context counterparty_type"
affects: [negotiation-loop, email-composition, counterparty-intelligence]

# Tech tracking
tech-stack:
  added: []
  patterns: [counterparty-adaptive-tone, prompt-context-injection]

key-files:
  created:
    - src/negotiation/counterparty/tone.py
    - tests/counterparty/test_tone.py
  modified:
    - src/negotiation/llm/prompts.py
    - src/negotiation/llm/composer.py
    - src/negotiation/llm/negotiation_loop.py
    - tests/llm/test_composer.py

key-decisions:
  - "Tone guidance injected in user prompt (not system prompt) to vary per-request without invalidating cached system prompt"
  - "Default tone is direct_influencer for backward compatibility when counterparty_type is missing/empty/None"

patterns-established:
  - "Counterparty context injection: tone guidance passed as formatted string through composer to LLM user prompt"

requirements-completed: [CPI-03]

# Metrics
duration: 2min
completed: 2026-03-08
---

# Phase 16 Plan 03: Tone Adjustment Summary

**Counterparty-adaptive tone guidance with data-backed style for talent managers and relationship-driven style for direct influencers, injected into LLM prompts via composer**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-08T22:21:04Z
- **Completed:** 2026-03-08T22:23:11Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- get_tone_guidance module returns professional/data-backed instructions for talent managers and warm/creative instructions for direct influencers
- Composer accepts counterparty_context parameter and injects it into the user prompt alongside lever instructions
- Negotiation loop reads counterparty_type and agency_name from context, generates tone guidance automatically
- All 121 existing tests pass unchanged (full backward compatibility)

## Task Commits

Each task was committed atomically:

1. **Task 1: Tone guidance module and tests** - `2f5d1f8` (feat)
2. **Task 2: Wire tone guidance into composer, prompts, and negotiation loop** - `23b81d6` (feat)

## Files Created/Modified
- `src/negotiation/counterparty/tone.py` - get_tone_guidance function with talent_manager and direct_influencer tone templates
- `tests/counterparty/test_tone.py` - 11 tests covering both counterparty types, agency name injection, and defaults
- `src/negotiation/llm/prompts.py` - Added {counterparty_context} placeholder in user prompt
- `src/negotiation/llm/composer.py` - Added counterparty_context parameter with empty string default
- `src/negotiation/llm/negotiation_loop.py` - Generates tone guidance from context and passes to composer
- `tests/llm/test_composer.py` - 2 new tests for counterparty context injection and default fallback

## Decisions Made
- Tone guidance injected in user prompt (not system prompt) to vary per-request without invalidating the cached system prompt
- Default tone is direct_influencer for backward compatibility when counterparty_type is missing, empty, or None
- Agency name is optional and appended to talent manager guidance when available (e.g., "from UTA")

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tone guidance is fully integrated into the negotiation pipeline
- Any future counterparty types can be added to tone.py with a new conditional branch
- Phase 16 counterparty intelligence feature set complete pending plan 02

## Self-Check: PASSED

- All 6 files verified present on disk
- Commit `2f5d1f8` (Task 1) found in git log
- Commit `23b81d6` (Task 2) found in git log
- 121/121 tests passing across counterparty/ and llm/ test suites

---
*Phase: 16-counterparty-intelligence*
*Completed: 2026-03-08*
