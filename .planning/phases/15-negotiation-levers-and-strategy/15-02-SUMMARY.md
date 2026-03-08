---
phase: 15-negotiation-levers-and-strategy
plan: 02
subsystem: negotiation
tags: [lever-engine, negotiation-loop, email-composer, prompts, integration]

requires:
  - phase: 15-negotiation-levers-and-strategy
    provides: "LeverAction, NegotiationLeverContext, LeverResult models and select_lever engine"
provides:
  - "Lever engine wired into negotiation loop for every COUNTER/QUESTION reply"
  - "Lever-adjusted rate and deliverables flow through to email composition"
  - "Escalation and graceful exit paths from lever engine"
  - "lever_instructions forwarded to LLM via prompts and composer"
affects: [15-03, app-orchestrator, email-templates]

tech-stack:
  added: []
  patterns: ["inline lever selection between pricing eval and email composition", "default lever context for backward compatibility"]

key-files:
  created: []
  modified:
    - src/negotiation/llm/prompts.py
    - src/negotiation/llm/composer.py
    - src/negotiation/llm/negotiation_loop.py
    - tests/llm/test_negotiation_loop.py

key-decisions:
  - "lever_instructions parameter placed after model param in composer for backward compat (keyword-only with default)"
  - "base_context test fixture updated with deliverable_scenarios to prevent graceful_exit on default context"
  - "Lever ceiling test uses rate within CPM ceiling but above max_cost_without_approval to isolate lever escalation from pricing escalation"

patterns-established:
  - "Lever result included in all action return dicts (send, escalate, exit) for caller tracking"
  - "Default lever context values (current_scenario=1, current_usage_tier=target, etc.) ensure backward compatibility"

requirements-completed: [NEG-09, NEG-10, NEG-11, NEG-12, NEG-14, NEG-15]

duration: 3min
completed: 2026-03-08
---

# Phase 15 Plan 02: Lever Engine Integration Summary

**Lever engine wired into negotiation loop with escalation/exit paths, lever-adjusted rates, and lever_instructions forwarded to LLM email composer**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T21:54:16Z
- **Completed:** 2026-03-08T21:57:48Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Lever engine called for every COUNTER/QUESTION reply via select_lever
- Escalation (NEG-12 ceiling) and graceful exit (NEG-15) paths integrated into loop
- Lever-adjusted rate and deliverables summary replace simple calculate_rate output
- lever_instructions flow from engine through composer to LLM prompt
- 3 new integration tests covering ceiling escalation, graceful exit, and lever forwarding
- 843 total tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Update prompts and composer to accept lever instructions** - `3a5b23e` (feat)
2. **Task 2: Integrate lever engine into negotiation loop** - `e1c1288` (feat)

## Files Created/Modified
- `src/negotiation/llm/prompts.py` - Added {lever_instructions} placeholder and lever rule to system prompt
- `src/negotiation/llm/composer.py` - Added lever_instructions parameter with empty string default
- `src/negotiation/llm/negotiation_loop.py` - Integrated select_lever call, escalation/exit handling, lever-adjusted rate/deliverables
- `tests/llm/test_negotiation_loop.py` - 3 new tests + updated base_context with deliverable_scenarios

## Decisions Made
- Placed lever_instructions parameter after model param in composer signature (keyword-only with default) to avoid breaking positional arg order
- Updated test base_context fixture with DeliverableScenarios so lever engine has a non-terminal action available
- Lever ceiling test isolates lever escalation from CPM ceiling by using rate within pricing bounds but above max_cost_without_approval

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lever_instructions parameter position in composer signature**
- **Found during:** Task 1
- **Issue:** Plan placed lever_instructions (with default) before client (no default), causing SyntaxError
- **Fix:** Moved lever_instructions after model parameter to maintain valid Python signature
- **Files modified:** src/negotiation/llm/composer.py
- **Verification:** Import succeeds, signature inspection passes
- **Committed in:** 3a5b23e (Task 1 commit)

**2. [Rule 1 - Bug] Updated test base_context with deliverable_scenarios**
- **Found during:** Task 2
- **Issue:** Existing tests failed because default lever context (no campaign data) falls through to graceful_exit
- **Fix:** Added DeliverableScenarios to base_context fixture so lever engine picks trade_deliverables
- **Files modified:** tests/llm/test_negotiation_loop.py
- **Verification:** All 9 existing tests pass, 3 new tests pass
- **Committed in:** e1c1288 (Task 2 commit)

**3. [Rule 1 - Bug] Adjusted ceiling test to isolate lever escalation from pricing escalation**
- **Found during:** Task 2
- **Issue:** proposed_rate of $5000 triggered CPM ceiling at Step 7 before reaching lever engine at Step 8.5
- **Fix:** Used rate $2800 (within CPM ceiling) with max_cost_without_approval $2000 so lever ceiling triggers
- **Files modified:** tests/llm/test_negotiation_loop.py
- **Verification:** test_lever_escalation_ceiling passes with lever engine reason
- **Committed in:** e1c1288 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Lever engine fully integrated into negotiation pipeline
- Every counter-offer email guided by appropriate lever tactic
- Ready for Plan 03 (orchestrator-level lever state tracking across rounds)

---
*Phase: 15-negotiation-levers-and-strategy*
*Completed: 2026-03-08*
