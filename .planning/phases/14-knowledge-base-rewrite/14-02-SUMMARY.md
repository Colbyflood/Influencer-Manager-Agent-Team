---
phase: 14-knowledge-base-rewrite
plan: 02
subsystem: knowledge-base
tags: [negotiation, knowledge-base, yaml-frontmatter, stage-filtering, llm-prompts]

requires:
  - phase: 14-knowledge-base-rewrite
    plan: 01
    provides: "9 email examples with YAML frontmatter for stage-aware filtering"
provides:
  - "Stage-aware knowledge base loading with load_examples_for_stage()"
  - "YAML frontmatter parsing for email example metadata filtering"
  - "Callers (negotiation_loop, app.py) pass negotiation stage to KB loader"
affects: [negotiation-llm, email-composition]

tech-stack:
  added: []
  patterns:
    - "YAML frontmatter parsing via yaml.safe_load with manual fallback"
    - "Stage-aware example selection: filter examples by negotiation stage and platform"
    - "Backward-compatible optional parameter pattern (stage=None preserves old behavior)"

key-files:
  created: []
  modified:
    - src/negotiation/llm/knowledge_base.py
    - src/negotiation/llm/prompts.py
    - src/negotiation/llm/negotiation_loop.py
    - src/negotiation/app.py
    - src/negotiation/llm/__init__.py
    - tests/llm/test_knowledge_base.py

key-decisions:
  - "Used yaml.safe_load with manual string-parse fallback for environments without PyYAML"
  - "Stage filtering uses list membership check on example frontmatter stages array"
  - "Platform-agnostic examples (platform: null) always included regardless of platform filter"

patterns-established:
  - "Knowledge base example filtering: parse frontmatter, filter by stage/platform, concatenate matches"
  - "Backward-compatible function extension: add optional parameter with None default"

requirements-completed: [KB-06]

duration: 3min
completed: 2026-03-08
---

# Phase 14 Plan 02: Stage-Aware Example Selection Summary

**Stage-aware KB loader with YAML frontmatter parsing, filtering examples by negotiation stage/platform, and caller integration in negotiation loop and app.py**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T21:29:08Z
- **Completed:** 2026-03-08T21:32:02Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added load_examples_for_stage() function with YAML frontmatter parsing and stage/platform filtering
- Updated load_knowledge_base() with optional stage parameter -- when provided, appends filtered examples under "Relevant Email Examples" heading
- Wired stage-aware loading into negotiation_loop.py (passes negotiation_stage from context) and app.py (passes "initial_offer" for outreach)
- Added 11 new tests covering stage filtering, platform filtering, backward compatibility, and real KB content verification
- Added style reference instruction to EMAIL_COMPOSITION_SYSTEM_PROMPT for email examples

## Task Commits

Each task was committed atomically:

1. **Task 1: Add stage-aware example loading to knowledge_base.py** - `9403deb` (feat)
2. **Task 2: Wire stage-aware loading into callers and add tests** - `92940fc` (feat)

## Files Created/Modified
- `src/negotiation/llm/knowledge_base.py` - Added _parse_frontmatter(), load_examples_for_stage(), updated load_knowledge_base() with stage param
- `src/negotiation/llm/prompts.py` - Added style reference instruction for email examples in system prompt
- `src/negotiation/llm/negotiation_loop.py` - Passes negotiation_stage to load_knowledge_base
- `src/negotiation/app.py` - Passes stage="initial_offer" to load_knowledge_base for outreach emails
- `src/negotiation/llm/__init__.py` - Exports load_examples_for_stage
- `tests/llm/test_knowledge_base.py` - Added TestLoadExamplesForStage (9 tests) and TestExportedSymbols (2 tests)

## Decisions Made
- Used yaml.safe_load with manual string-parse fallback for portability across environments
- Platform-agnostic examples (platform: null) always included when platform filter is provided
- Stage filtering checks list membership on the example's stages array
- Empty string returned when no examples match (not an error) for graceful degradation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing anthropic module import error prevents pytest collection of test_knowledge_base.py through the normal import chain (ModuleNotFoundError in src/negotiation/llm/client.py). This is the same issue documented in 14-01-SUMMARY.md. All test logic was verified correct via direct execution with mocked anthropic module.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Stage-aware knowledge base loading is fully integrated into both negotiation paths
- Counter-offer emails will now receive stage-relevant examples (bundled_rate, cpm_mention for counter_sent; positive_close for agreed)
- Initial outreach emails receive initial_offer stage examples (bundled_rate)
- All backward compatibility preserved for any callers not yet passing stage parameter

---
*Phase: 14-knowledge-base-rewrite*
*Completed: 2026-03-08*
