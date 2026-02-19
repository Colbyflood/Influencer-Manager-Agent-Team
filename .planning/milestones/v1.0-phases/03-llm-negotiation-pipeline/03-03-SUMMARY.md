---
phase: 03-llm-negotiation-pipeline
plan: 03
subsystem: llm
tags: [anthropic, email-composition, validation-gate, regex, pydantic, prompt-caching]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Pydantic models (ComposedEmail, ValidationFailure, ValidationResult), prompt templates (EMAIL_COMPOSITION_SYSTEM_PROMPT, EMAIL_COMPOSITION_USER_PROMPT), client constants (COMPOSE_MODEL)"
provides:
  - "compose_counter_email function using Claude API with KB-injected system prompt and prompt caching"
  - "validate_composed_email deterministic gate with 5 checks (monetary, deliverables, hallucinations, forbidden phrases, sanity)"
affects: [03-04-PLAN, negotiation-loop, escalation-routing]

# Tech tracking
tech-stack:
  added: []
  patterns: [prompt-caching-with-cache-control-ephemeral, deterministic-validation-gate, regex-based-email-validation]

key-files:
  created:
    - src/negotiation/llm/composer.py
    - src/negotiation/llm/validation.py
    - tests/llm/test_composer.py
    - tests/llm/test_validation.py
  modified:
    - src/negotiation/llm/__init__.py

key-decisions:
  - "Used type: ignore[union-attr] for response.content[0].text since Anthropic SDK returns Union type for content blocks"
  - "Validation gate uses only regex and string matching -- zero LLM calls for 100% deterministic behavior"
  - "Missing deliverables produce warnings (not errors) to avoid blocking emails over minor phrasing differences"
  - "Dollar amount validation rejects ANY non-matching monetary value in the email to prevent rate confusion"

patterns-established:
  - "Prompt caching: cache_control={'type': 'ephemeral'} on system content blocks for KB cost savings"
  - "Validation severity: 'error' blocks sending, 'warning' logs but allows sending"
  - "Dollar normalization: strip $ and commas before comparing to expected Decimal rate"

requirements-completed: [NEG-06]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 3 Plan 03: Email Composition and Validation Gate Summary

**Counter-offer email composer with Claude API prompt caching and 5-check deterministic validation gate catching monetary mismatches, hallucinated commitments, and off-brand language**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T01:50:46Z
- **Completed:** 2026-02-19T01:53:54Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 5

## Accomplishments
- Built compose_counter_email that generates counter-offer emails using Claude Sonnet with knowledge base content injected via cached system prompts (90% cost savings on repeated KB)
- Created validate_composed_email deterministic gate with 5 checks: monetary value matching, deliverable coverage (warning-only), hallucinated commitment detection, forbidden phrase filtering, and minimum length sanity
- 20 tests covering all validation edge cases (6 composer, 14 validation) -- all passing with ruff clean and mypy strict clean
- Updated __init__.py to re-export both compose_counter_email and validate_composed_email for clean package imports

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Write failing tests for composer and validation** - `49d19c8` (test)
2. **Task 2 (GREEN): Implement composer.py and validation.py** - `e362597` (feat)

No refactor commit needed -- implementation was clean after GREEN phase.

## Files Created/Modified
- `src/negotiation/llm/composer.py` - compose_counter_email function with Claude API calls, prompt caching, and token tracking
- `src/negotiation/llm/validation.py` - validate_composed_email with 5 deterministic checks using regex and string matching
- `src/negotiation/llm/__init__.py` - Updated re-exports for compose_counter_email and validate_composed_email
- `tests/llm/test_composer.py` - 6 tests with mocked Anthropic client for prompt injection, cache_control, and model selection
- `tests/llm/test_validation.py` - 14 tests for monetary values, hallucinated commitments, deliverable coverage, forbidden phrases, too-short emails, and multiple failure collection

## Decisions Made
- Used `type: ignore[union-attr]` for `response.content[0].text` since Anthropic SDK content blocks are a Union type and mypy cannot narrow without runtime isinstance
- Validation gate is 100% deterministic (regex + string matching only) -- no LLM validates LLM output, per project design decision
- Missing deliverables produce warnings (not errors) to avoid blocking emails when the LLM uses slightly different phrasing for the same deliverable
- All dollar amounts in the email must exactly match the expected rate -- any extra or mismatched monetary value is an error to prevent rate confusion

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff format issue in validation.py**
- **Found during:** Task 2 (GREEN implementation)
- **Issue:** ruff format check failed on validation.py (unnecessary parentheses in f-string)
- **Fix:** Applied `ruff format` to validation.py
- **Files modified:** src/negotiation/llm/validation.py
- **Verification:** `uv run ruff format --check` passes clean
- **Committed in:** e362597 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (formatting)
**Impact on plan:** Standard formatting compliance. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Tests use mocked Anthropic client.

## Next Phase Readiness
- compose_counter_email ready for use in negotiation loop (Plan 03-04)
- validate_composed_email ready to gate email sending -- returns passed=False to trigger escalation routing
- Both functions importable from `negotiation.llm` package
- Ready for Plan 03-04 (Negotiation Loop orchestration)

## Self-Check: PASSED

All 5 key files verified present. Both commit hashes (49d19c8, e362597) verified in git log. All artifact minimum line counts met (composer: 89/30, validation: 153/50, test_composer: 147/40, test_validation: 270/80).

---
*Phase: 03-llm-negotiation-pipeline*
*Completed: 2026-02-19*
