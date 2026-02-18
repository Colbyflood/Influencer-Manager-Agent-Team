# Architecture

**Analysis Date:** 2026-02-18

## Pattern Overview

**Overall:** Multi-Agent Orchestration Framework — GSD (Get Shit Done) is a Claude-native project delivery system that coordinates multiple specialized AI agents (themselves defined as markdown prompts) through a centralized orchestrator. The system decomposes complex software delivery into phases, which contain discrete execution plans with dependency tracking, verification checkpoints, and human decision gates.

**Key Characteristics:**
- **Agent-based architecture** — Each workflow role (planner, executor, verifier, researcher) is a discrete markdown agent definition spawned by orchestrator via Task() API
- **Context-conscious design** — Each agent has a 200k token budget. Orchestrators stay lean (~10-15% context) by delegating work to subagents with fresh context
- **Declarative planning** — Work is specified through markdown templates (PLAN.md, DISCOVERY.md, etc.) that become prompts; no code generation for delivery
- **Wave-based execution** — Tasks within a phase are grouped into dependency waves; Wave 1 runs in parallel, Wave 2 depends on Wave 1, etc.
- **Verification-gated workflow** — Every phase creates VERIFICATION.md and UAT.md artifacts. Gaps trigger gap-closure loop (`/gsd:plan-phase --gaps`)
- **Atomic commits** — Each task within a plan produces a single git commit; phase completion is atomically trackable

## Layers

**Orchestration Layer:**
- Purpose: Coordinates agent spawning, dependency resolution, wave management, checkpoint handling
- Location: `./.claude/get-shit-done/workflows/` (32 workflow files)
- Contains: Workflow specifications (new-project.md, execute-phase.md, verify-phase.md, etc.)
- Depends on: gsd-tools.cjs CLI, agent definitions, project state (ROADMAP.md, STATE.md)
- Used by: User invokes via `/gsd:*` slash commands; orchestrator spawns agents via Task()

**Agent Layer:**
- Purpose: Specialized roles (planner, executor, verifier, researcher, debugger) that implement specific workflow steps
- Location: `./.claude/agents/` (11 agent definitions)
- Contains: Agent role specifications, prompts, decision trees, tool usage patterns
- Examples: `gsd-planner.md` (creates executable plans), `gsd-executor.md` (implements tasks), `gsd-verifier.md` (validates must-haves)
- Depends on: Tools (Read, Write, Bash, Grep, Glob), project context files
- Used by: Orchestrator spawns agents when specific work needs to be done

**CLI/Tool Layer:**
- Purpose: Provides gsd-tools.cjs — JavaScript utility for file operations, git integration, config management, state queries
- Location: `./.claude/get-shit-done/bin/gsd-tools.cjs`
- Contains: 40+ command implementations (init, commit, config-get/set, phase-plan-index, roadmap update, etc.)
- Depends on: Node.js, git, file system
- Used by: All agents and orchestrators invoke gsd-tools for deterministic file operations, state queries, git commits

**Template Layer:**
- Purpose: Provides markdown templates that agents and workflows fill in
- Location: `./.claude/get-shit-done/templates/` (26 templates)
- Categories:
  - **Project templates**: project.md, requirements.md, roadmap.md (for `/gsd:new-project`)
  - **Codebase templates**: STACK.md, ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md (for `/gsd:map-codebase`)
  - **Research templates**: FEATURES.md, ARCHITECTURE.md, PITFALLS.md, STACK.md (for project research)
  - **Planning templates**: PLAN.md (for task execution), DISCOVERY.md, CONTEXT.md (for phase planning)
  - **Verification templates**: VERIFICATION.md, UAT.md (for `/gsd:verify-phase`)
- Depends on: None
- Used by: Agents read templates, fill placeholders, and write to `.planning/` directory

**State Layer:**
- Purpose: Persistent project state tracked in markdown files
- Location: `.planning/` directory structure
- Key files:
  - `PROJECT.md` — Core project vision (from new-project)
  - `ROADMAP.md` — Phase breakdown with requirements mapping
  - `REQUIREMENTS.md` — Feature list with REQ-ID traceability
  - `STATE.md` — Current project position (phase number, decisions, blockers)
  - `config.json` — Workflow preferences (mode, depth, parallelization, AI models)
  - `phases/{phase-name}/*-PLAN.md` — Executable task breakdown
  - `phases/{phase-name}/*-SUMMARY.md` — Execution output and artifacts created
  - `research/` — Research outputs (STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md)
  - `debug/` — Problem investigation sessions
- Depends on: gsd-tools.cjs for deterministic reads/writes
- Used by: All agents read STATE files to understand context; agents write SUMMARY/VERIFICATION files to record progress

**Command Layer:**
- Purpose: Expose workflows as user-invoked commands
- Location: `./.claude/commands/gsd/` (21 command definitions)
- Contains: Command metadata and workflow routing
- Examples: `plan-phase.md` (routes to planner), `execute-phase.md` (routes to executor), `research-phase.md` (routes to researchers)
- Depends on: Workflows
- Used by: User types `/gsd:command-name` in Claude Code; Claude Code reads command definition and invokes associated workflow

## Data Flow

**Project Initialization Flow:**

1. User: `/gsd:new-project`
2. Orchestrator (new-project.md):
   - Validates project doesn't exist
   - Captures vision through questioning
   - Writes PROJECT.md
   - Optionally runs parallel research (4 researchers → synthesizer)
   - Gathers requirements (interactive or auto)
   - Spawns roadmapper with REQUIREMENTS.md + RESEARCH.md
   - Roadmapper writes ROADMAP.md, STATE.md, updates REQUIREMENTS.md
   - Result: Roadmap with N phases, each mapped to specific requirements

**Phase Planning Flow:**

1. User: `/gsd:plan-phase N`
2. Orchestrator (plan-phase.md):
   - Loads ROADMAP.md, REQUIREMENTS.md, STATE.md
   - Optionally spawns researcher for domain-specific context
   - Planner reads ROADMAP entry for phase N
   - Planner decomposes into tasks, analyzes dependencies
   - Planner writes PLAN.md file(s) with:
     - Task breakdown (files, action, verify, done)
     - Dependency graph (needs/creates)
     - Wave structure (groups tasks for parallel execution)
     - Must-haves (goal-backward derived truths, artifacts, wiring)
   - Planner commits PLAN.md
   - Optional: Checker agent verifies PLAN.md will achieve phase goal
   - Result: Ready-to-execute plans grouped into waves

**Phase Execution Flow:**

1. User: `/gsd:execute-phase N`
2. Orchestrator (execute-phase.md):
   - Discovers plans in phase directory
   - Groups by wave number
   - Spawns executor agents (one per plan) in parallel within each wave
   - Each executor:
     - Reads PLAN.md
     - Executes each task: creates files, runs commands, commits
     - Writes SUMMARY.md with artifacts created
     - Updates STATE.md with progress
   - Orchestrator waits for wave completion, moves to next wave
   - Between waves: Handles checkpoint tasks (human verify, decision, human action)
   - After all waves: Spawns verifier to check must-haves
   - Result: CODE executed, files written, git commits created, SUMMARY.md documents artifacts

**Verification & Gap Closure Flow:**

1. User: `/gsd:verify-phase N`
2. Verifier agent:
   - Reads phase PLAN.md must-haves (truths, artifacts, key_links)
   - Inspects actual codebase (uses grep, file reads)
   - Writes VERIFICATION.md with:
     - Status: passed / gaps_found / human_needed
     - Gaps section: truth, reason, artifacts, missing items
   - If gaps found → updates roadmap to offer `/gsd:plan-phase N --gaps`
3. If gaps exist:
   - Planner (gap mode) reads VERIFICATION.md
   - Groups gaps by artifact, creates gap-closure plans
   - Plans written as phase N.1, N.2, etc. (decimal notation)
   - Executor runs gap plans → fixes artifacts
   - Verifier re-runs → confirms gaps closed

**State Management:**

- **Centralized in `.planning/` directory** — Single source of truth for project state
- **Atomic writes via gsd-tools.cjs** — All state updates go through CLI to prevent race conditions
- **Incremental updates** — Agent writes extend existing files rather than replacing (e.g., ROADMAP.md adds phase entry, doesn't rewrite whole file)
- **Version tracking via git commits** — Each agent commits after writing state artifacts
- **Recovery via STATE.md** — If context is lost, STATE.md tracks current phase number, completed plans, decision history

## Key Abstractions

**Phase:**
- Purpose: Represents a complete feature/capability that ships together
- Examples: `01-foundation`, `02-user-auth`, `03-dashboard`
- Pattern: Mapped to 1+ requirements from REQUIREMENTS.md; contains 1-10 plans; produces ROADMAP entry with goal + success criteria

**Plan:**
- Purpose: Single executable unit containing 2-3 tasks that work together
- Examples: `01-01-PLAN.md` (foundation plan 1)
- Pattern: Contains YAML frontmatter (phase, plan, wave, depends_on, files_modified), objective, task list, must-haves, verification
- Constraint: Fits within ~50% of executor's context budget; tasks are 15-60 minutes each

**Task:**
- Purpose: Smallest unit of work — produces one or more files via single action
- Examples: "Create User model", "Add login endpoint", "Write dashboard component"
- Pattern: Contains name, files (paths), action (specific instructions), verify (command/check), done (acceptance criteria)
- Constraint: Autonomous tasks run without checkpoints; checkpoint tasks pause for human input

**Wave:**
- Purpose: Groups of tasks that run in parallel (within a wave) or sequentially (wave 1, then wave 2, etc.)
- Pattern: All tasks in a wave have no inter-dependencies; Wave N+1 depends on Wave N
- Used in: Execution orchestration for parallelism optimization

**Must-Have:**
- Purpose: Goal-backward specification — defines truths that MUST be observable for phase goal to be met
- Components: Truths (observable behaviors), Artifacts (files that must exist), Key Links (critical connections)
- Pattern: Derived BEFORE implementation; verified AFTER phase completion
- Used in: Verification to confirm phase success without checking every file

**Checkpoint:**
- Purpose: Human decision point or verification gate during execution
- Types: `checkpoint:human-verify` (confirm auto-work), `checkpoint:decision` (pick approach), `checkpoint:human-action` (unavoidable manual step)
- Pattern: Task with type="checkpoint:*" and no action element; executor pauses, returns state, awaits user response
- Used in: Interactive workflows where human judgment needed

**Research Output:**
- Purpose: Domain-specific findings that inform requirements and planning
- Examples: STACK.md (tech recommendations), FEATURES.md (feature categories), ARCHITECTURE.md (system design patterns), PITFALLS.md (gotchas)
- Pattern: Written by researcher agents for specific phase or project
- Used in: Roadmapper reads SUMMARY.md; Planner reads relevant research

## Entry Points

**User Commands (31 slash commands):**
- Location: `./.claude/commands/gsd/`
- Triggers: User types `/gsd:command-name [args]`
- Responsibilities: Route to appropriate workflow, load context, spawn agents
- Examples:
  - `/gsd:new-project` — Initialize project (calls new-project.md workflow)
  - `/gsd:plan-phase N` — Create execution plans for phase N
  - `/gsd:execute-phase N` — Run all plans for phase N
  - `/gsd:verify-phase N` — Check if phase met its goals
  - `/gsd:research-phase N` — Gather domain context before planning

**Workflow Entry Points (32 workflows):**
- Location: `./.claude/get-shit-done/workflows/`
- Triggers: Invoked by slash commands
- Responsibilities: Orchestrate agents, handle branching logic, manage checkpoints
- Examples: `new-project.md` (5000+ lines, multi-step init), `execute-phase.md` (2000+ lines, wave orchestration)

**Agent Entry Points (11 agents):**
- Location: `./.claude/agents/`
- Triggers: Spawned by orchestrator via Task() with context
- Responsibilities: Execute specific workflow step (research, planning, execution, verification)
- Examples: `gsd-planner.md` (1200+ lines, plan creation), `gsd-executor.md` (1100+ lines, task execution)

## Error Handling

**Strategy:** Multi-layered — orchestrator coordinates, agents report, CLI validates.

**Patterns:**

1. **Validation Errors** (user input issues)
   - Caught by: Orchestrator checks (project exists? phase number valid?)
   - Pattern: Early exit with clear error message before spawning agents
   - Example: `/gsd:execute-phase 99` when only 5 phases exist

2. **Agent Failure** (execution error)
   - Caught by: Executor agent detects failed task
   - Pattern: Agent returns FAILED status, orchestrator presents options ("Retry?", "Continue with next plan?", "Stop?")
   - Recovery: User retries or skips; partial progress tracked in STATE.md

3. **Verification Failure** (output doesn't match must-haves)
   - Caught by: Verifier agent during `/gsd:verify-phase`
   - Pattern: Generates VERIFICATION.md with gaps section; orchestrator offers gap closure (`/gsd:plan-phase N --gaps`)
   - Recovery: Gap-closure plans created to fix artifacts

4. **Git Commit Failure** (permissions, merge conflicts)
   - Caught by: gsd-tools.cjs commit wrapper
   - Pattern: Logs error, agent stops, user gets message
   - Recovery: User fixes (resolve conflict, fix permissions), agent retries manually

5. **Context Exhaustion** (agent runs out of tokens)
   - Caught by: Claude Code timeout
   - Pattern: Task blocks, orchestrator detects no response
   - Recovery: User re-runs phase execution; STATE.md tracks progress; execution resumes from incomplete plans

6. **Known Bug Handling** (classifyHandoffIfNeeded)
   - Caught by: Execute-phase orchestrator
   - Pattern: Agent reports failure with specific error text; orchestrator spot-checks (SUMMARY.md exists? Commits present?); if spot-checks pass, treats as success
   - Rationale: Claude Code SDK bug fires AFTER all work completes, false negative

## Cross-Cutting Concerns

**Logging:** No centralized logging framework. Agents use console output (visible in Claude Code) and structured markdown output files (SUMMARY.md, VERIFICATION.md) for audit trail.

**Validation:** Two-phase approach:
- **Frontmatter validation** — gsd-tools.cjs validates YAML frontmatter in PLAN.md (required fields, data types)
- **Content validation** — Verifier agent validates against must-haves (truths observable in code, artifacts exist, key links present)

**Authentication:** No built-in auth. Assumes Claude Code runs in user's authenticated terminal with git credentials. External service auth (APIs, databases) managed via environment variables (.env files, explicitly excluded from codebase mapping).

**Parallelism:** Managed at wave level. gsd-tools.cjs `phase-plan-index` groups plans by wave number. Orchestrator spawns Task() for each plan in a wave (runs in parallel), waits for all to complete, then moves to next wave. Fine-grained parallelism depends on Claude Code's Task() implementation.

**State Consistency:** Enforced by atomic git commits. Each agent task produces one commit; agents read committed state before writing. No race conditions between agents because waves are sequential (Wave 1 completes → Wave 2 starts).

**Tool Access:** All agents have access to core tools (Read, Write, Bash, Grep, Glob). Special agents like executor also use Task() to spawn subagents. No agent-to-agent communication except through filesystem state (files).

---

*Architecture analysis: 2026-02-18*
