# Codebase Structure

**Analysis Date:** 2026-02-18

## Directory Layout

```
.claude/
├── agents/                          # Agent role definitions (11 files)
│   ├── gsd-planner.md              # Creates executable plans from phase requirements
│   ├── gsd-executor.md             # Implements tasks in plans (writes code, creates files)
│   ├── gsd-verifier.md             # Validates phase output against must-haves
│   ├── gsd-debugger.md             # Diagnoses broken functionality
│   ├── gsd-phase-researcher.md     # Researches specific domain for phase context
│   ├── gsd-project-researcher.md   # Researches tech stack, features, architecture
│   ├── gsd-research-synthesizer.md # Synthesizes research outputs
│   ├── gsd-plan-checker.md         # Validates plans will achieve phase goal
│   ├── gsd-roadmapper.md           # Creates delivery roadmap from requirements
│   ├── gsd-integration-checker.md  # Verifies external service integrations work
│   └── gsd-codebase-mapper.md      # Maps existing codebase structure
│
├── commands/
│   └── gsd/                         # Command routing (21 files)
│       ├── new-project.md           # Initialize project
│       ├── plan-phase.md            # Create plans for a phase
│       ├── execute-phase.md         # Run plans for a phase
│       ├── verify-phase.md          # Check phase completion
│       ├── research-phase.md        # Research before planning
│       ├── discuss-phase.md         # Gather context for phase
│       ├── progress.md              # Show project status
│       ├── complete-milestone.md    # Mark milestone done
│       ├── check-todos.md           # Review pending work
│       └── [16 other commands]
│
├── get-shit-done/                   # Framework core
│   ├── VERSION                      # Framework version (1.20.4)
│   ├── bin/
│   │   └── gsd-tools.cjs           # CLI utility (40+ commands, deterministic file ops)
│   │
│   ├── workflows/                   # Orchestration workflows (32 files)
│   │   ├── new-project.md          # Project initialization (5000+ lines)
│   │   ├── execute-phase.md        # Wave-based execution (2000+ lines)
│   │   ├── plan-phase.md           # Phase planning orchestration
│   │   ├── verify-phase.md         # Phase verification
│   │   ├── research-phase.md       # Pre-planning research
│   │   ├── discuss-phase.md        # Phase context gathering
│   │   ├── execute-plan.md         # Single plan execution (executor reads this)
│   │   ├── check-todos.md          # Review pending work
│   │   ├── health.md               # Diagnostic checks
│   │   └── [23 other workflows]
│   │
│   ├── references/                  # Reference documentation (8 files)
│   │   ├── checkpoints.md          # Checkpoint syntax and patterns
│   │   ├── tdd.md                  # Test-driven development workflow
│   │   ├── continuation-prompt.md  # Resume agents after checkpoints
│   │   ├── summary.md              # SUMMARY.md template
│   │   └── [4 other references]
│   │
│   ├── templates/                   # Markdown templates (26 files)
│   │   ├── project.md              # PROJECT.md template
│   │   ├── roadmap.md              # ROADMAP.md template
│   │   ├── requirements.md         # REQUIREMENTS.md template
│   │   ├── codebase/               # Codebase mapping templates
│   │   │   ├── STACK.md            # Technology stack template
│   │   │   ├── ARCHITECTURE.md     # Architecture template
│   │   │   ├── STRUCTURE.md        # Structure template
│   │   │   ├── CONVENTIONS.md      # Coding conventions template
│   │   │   ├── TESTING.md          # Testing patterns template
│   │   │   └── CONCERNS.md         # Technical debt template
│   │   ├── research-project/       # Project research templates
│   │   │   ├── STACK.md            # Technology stack research
│   │   │   ├── FEATURES.md         # Feature categories research
│   │   │   ├── ARCHITECTURE.md     # Architecture patterns research
│   │   │   ├── PITFALLS.md         # Common pitfalls research
│   │   │   └── SUMMARY.md          # Research synthesis
│   │   └── [other templates]
│   │
│   └── references/                  # Support documentation
│       └── [diagnostic and reference docs]
│
├── settings.json                   # Global settings
└── gsd-file-manifest.json          # File inventory (for discovery)

.planning/                          # Project state directory (user-created)
├── PROJECT.md                      # Project vision and core requirements
├── ROADMAP.md                      # Phase breakdown with requirement mapping
├── REQUIREMENTS.md                 # Feature list (v1/v2/out of scope) with REQ-IDs
├── STATE.md                        # Current project position
├── config.json                     # Workflow config (mode, depth, parallelization, AI models)
├── codebase/                       # Codebase analysis (from /gsd:map-codebase)
│   ├── STACK.md                    # Technology stack
│   ├── ARCHITECTURE.md             # System architecture
│   ├── STRUCTURE.md                # Directory structure
│   ├── CONVENTIONS.md              # Coding conventions
│   ├── TESTING.md                  # Testing patterns
│   ├── INTEGRATIONS.md             # External service integrations
│   └── CONCERNS.md                 # Technical debt and issues
├── research/                       # Project research (from /gsd:new-project)
│   ├── STACK.md                    # Tech stack research
│   ├── FEATURES.md                 # Feature categories
│   ├── ARCHITECTURE.md             # Architecture patterns
│   ├── PITFALLS.md                 # Common gotchas
│   └── SUMMARY.md                  # Research synthesis
├── phases/                         # Phase execution artifacts
│   ├── 01-foundation/
│   │   ├── 01-01-PLAN.md           # Executable task plan
│   │   ├── 01-01-SUMMARY.md        # Execution output and artifacts
│   │   ├── 01-02-PLAN.md
│   │   ├── 01-02-SUMMARY.md
│   │   ├── 01-VERIFICATION.md      # Phase goal verification
│   │   └── 01-UAT.md               # User acceptance test results
│   ├── 02-user-auth/
│   │   ├── 02-01-PLAN.md
│   │   ├── 02-01-SUMMARY.md
│   │   └── [more plans/summaries]
│   └── [more phases]
└── debug/                          # Problem investigations
    ├── session-slug.md             # Individual debug session
    └── resolved/                   # Completed investigations
        └── [resolved sessions]

.git/                               # Version control
└── hooks/                          # Git hooks (in .claude/hooks/)

CLAUDE.md                           # Project guidance for Claude Code
```

## Directory Purposes

**`.claude/agents/`:**
- Purpose: Agent role definitions (markdown prompts defining how specialized agents behave)
- Contains: 11 markdown files, each 1000-2000 lines, defining a single agent's responsibilities, decision trees, prompts
- Key files:
  - `gsd-planner.md` — Decompose phase into tasks, analyze dependencies, write PLAN.md
  - `gsd-executor.md` — Execute tasks from PLAN.md, create files, run commands, commit, write SUMMARY.md
  - `gsd-verifier.md` — Check phase against must-haves, write VERIFICATION.md, diagnose gaps
- How it's used: Orchestrators spawn these agents via Task() API when specific work needs specialized handling

**`.claude/commands/gsd/`:**
- Purpose: Command entry points (routing and metadata)
- Contains: 21 markdown files, each describing a user-accessible `/gsd:command`
- Each file includes: command name, description, workflow reference, argument parsing
- How it's used: Claude Code reads command file when user types `/gsd:command-name`

**`.claude/get-shit-done/workflows/`:**
- Purpose: Orchestration logic (master workflows that coordinate agents and state)
- Contains: 32 markdown files ranging from 500 to 5000+ lines
- Key workflows:
  - `new-project.md` — Initialize project (questioning → research → requirements → roadmap)
  - `execute-phase.md` — Run all plans in a phase (wave orchestration, checkpoints, verification)
  - `plan-phase.md` — Create executable plans from phase requirements
  - `verify-phase.md` — Check if phase achieved its goal (may trigger gap closure)
- How it's used: Orchestrator reads and follows workflow steps, spawns agents, interprets results

**`.claude/get-shit-done/bin/`:**
- Purpose: CLI utility (deterministic file operations, state queries, git automation)
- Contains: `gsd-tools.cjs` (JavaScript, 189KB, 40+ command implementations)
- Key commands:
  - `init {context}` — Load project initialization context
  - `commit {message} --files {paths}` — Atomic git commit (handles multi-file, commit message formatting)
  - `config-get/set {key}` — Read/write `.planning/config.json`
  - `phase-plan-index {phase}` — Get plans grouped by wave
  - `roadmap get-phase {N}` — Query phase from ROADMAP.md
  - `frontmatter validate {file}` — Validate YAML frontmatter structure
- How it's used: All agents and orchestrators invoke via `node ./.claude/get-shit-done/bin/gsd-tools.cjs {command}`

**`.claude/get-shit-done/templates/`:**
- Purpose: Markdown templates that agents fill in and write
- Contains: 26 files organized by category
- Categories:
  - **Project templates** (`project.md`, `roadmap.md`, `requirements.md`) — Used by new-project workflow
  - **Codebase templates** (`STACK.md`, `ARCHITECTURE.md`, etc.) — Used by codebase-mapper agent
  - **Research templates** (in `research-project/` subdirectory) — Used by researcher agents
  - **Planning templates** (`PLAN.md`, `DISCOVERY.md`) — Used by planner agent
  - **Verification templates** (`VERIFICATION.md`, `UAT.md`) — Used by verifier agent
- How it's used: Agents read template, replace placeholders, write filled version to `.planning/`

**`.planning/`:**
- Purpose: Project state directory (user-created by `/gsd:new-project`)
- Contains: Markdown files representing project vision, requirements, roadmap, execution state
- Key structure:
  - **Root files** (`PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`, `config.json`) — Project-level metadata
  - **`phases/{phase-name}/`** — Execution artifacts for each phase (PLAN.md, SUMMARY.md, VERIFICATION.md, UAT.md)
  - **`research/`** — Domain research outputs (STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md, SUMMARY.md)
  - **`codebase/`** — Codebase mapping outputs (STACK.md, ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, INTEGRATIONS.md, CONCERNS.md)
  - **`debug/`** — Problem investigation sessions
- How it's used: All agents read/write to `.planning/`; git tracks all changes for audit trail

## Key File Locations

**Entry Points:**
- `/gsd:command-name` — User invokes via Claude Code slash command interface
- `./.claude/commands/gsd/{command}.md` — Command definition (metadata, workflow routing)
- `./.claude/get-shit-done/workflows/{workflow}.md` — Orchestration logic (steps, agent spawning)

**Configuration:**
- `.planning/config.json` — Project workflow preferences (mode: yolo/interactive, depth: quick/standard/comprehensive, parallelization, AI models)
- `.planning/PROJECT.md` — Project vision, core requirements, key decisions
- `.claude/settings.json` — Global framework settings

**Core Logic:**
- `./.claude/get-shit-done/bin/gsd-tools.cjs` — Deterministic file operations, git automation, state queries
- `./.claude/agents/gsd-planner.md` — Task decomposition, dependency analysis, PLAN.md creation
- `./.claude/agents/gsd-executor.md` — File creation, command execution, git commits, SUMMARY.md writing
- `./.claude/agents/gsd-verifier.md` — Must-have validation, gap detection, VERIFICATION.md writing
- `./.claude/get-shit-done/workflows/execute-phase.md` — Wave orchestration, checkpoint handling, agent spawning

**Testing:**
- `./.claude/get-shit-done/bin/gsd-tools.test.cjs` — Unit tests for gsd-tools.cjs (87KB, comprehensive test suite)

## Naming Conventions

**Files:**
- **Workflow files**: kebab-case with `.md` extension (`new-project.md`, `execute-phase.md`)
- **Agent definitions**: prefix `gsd-` + kebab-case (`gsd-planner.md`, `gsd-executor.md`)
- **Command files**: kebab-case matching command name (`plan-phase.md` for `/gsd:plan-phase`)
- **Project state**: UPPERCASE with `.md` extension (`PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`)
- **Plan files**: numbered with phase/plan number (`01-01-PLAN.md`, `02-03-PLAN.md`)
- **Summary files**: numbered with phase/plan number (`01-01-SUMMARY.md`)
- **Verification files**: phase number + purpose (`01-VERIFICATION.md`, `01-UAT.md`, `01-CONCERNS.md`)

**Directories:**
- **Framework**: `.claude/` (hidden, contains agents/commands/workflows)
- **Project state**: `.planning/` (created by projects, contains all analysis and planning)
- **Phase artifacts**: `.planning/phases/{phase-slug}/` (e.g., `01-foundation`, `02-user-auth`)
- **Research output**: `.planning/research/` (parallel research sessions stored here)
- **Codebase analysis**: `.planning/codebase/` (map-codebase outputs)

## Where to Add New Code

**New Workflow (orchestration step):**
- Primary code: `./.claude/get-shit-done/workflows/{name}.md`
- Pattern: Copy existing workflow (e.g., `execute-phase.md`), adapt steps, preserve `<step name="">` structure
- Must include: `<process>`, `<step>` elements, agent spawning via Task(), state loading/writing
- Register: Add reference in appropriate command file (`./.claude/commands/gsd/{command}.md`)

**New Agent Role:**
- Primary code: `./.claude/agents/gsd-{role-name}.md`
- Pattern: Copy existing agent (e.g., `gsd-executor.md`), define `<role>`, `<process>` with steps, tools used
- Key sections: role definition, discovery levels (if applicable), tool usage patterns, success criteria
- Register: Reference in workflow that spawns it via Task(subagent_type="gsd-{role-name}")

**New Command:**
- Primary code: `./.claude/commands/gsd/{command-name}.md`
- Pattern: Metadata header (name, description, tools, color) + reference to workflow
- Pattern: One command → one workflow (commands are routing, workflows do real work)

**New Template:**
- Primary code: `./.claude/get-shit-done/templates/{category}/{name}.md`
- Pattern: Copy similar template, mark placeholders with `[Placeholder text]`
- Must include: Clear instructions for agent filling it in, marked sections for replacement
- Used by: Agents read template via Read tool, fill via string replacement, write via Write tool

**Modifying gsd-tools.cjs:**
- Location: `./.claude/get-shit-done/bin/gsd-tools.cjs`
- Pattern: Add new command in main switch statement, follow existing command pattern (parse args, interact with filesystem, return JSON)
- Must include: Corresponding test in `gsd-tools.test.cjs`
- Testing: `node ./.claude/get-shit-done/bin/gsd-tools.test.cjs`

**Adding a new workflow step:**
- Pattern: Add `<step name="descriptive-name">` element in workflow `<process>` section
- Must include: `<step name="">` (required for parsing), clear instructions, bash commands, or agent spawning
- Critical: Preserve variable scoping — use bash variable names consistently across steps

## Special Directories

**`.claude/`:**
- Purpose: GSD framework (not user-edited)
- Generated: No, committed to repo
- Committed: Yes — this is framework code

**`.planning/`:**
- Purpose: Project state and analysis (user-generated, created by `/gsd:new-project`)
- Generated: Yes — agents write analysis and planning documents
- Committed: Yes (by default), unless user chose `commit_docs: false` in config.json

**`.planning/phases/`:**
- Purpose: Execution artifacts for each phase
- Generated: Yes — agents write PLAN.md, SUMMARY.md, VERIFICATION.md
- Committed: Yes — each task produces atomic git commits via gsd-tools.cjs

**`.planning/debug/`:**
- Purpose: Problem investigation sessions (created by `/gsd:debug-phase` or when issues detected)
- Generated: Yes — debugger agent writes investigation sessions
- Committed: Yes, until resolved, then moved to `debug/resolved/`

**`.planning/research/`:**
- Purpose: Domain research outputs (created during `/gsd:new-project` if research selected)
- Generated: Yes — researcher agents write STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md
- Committed: Yes — feeds into roadmap creation

**`node_modules/`:**
- Purpose: npm dependencies (only contains gsd-tools test deps if exist)
- Generated: Yes — created by npm install
- Committed: No — in .gitignore

## Workflow-to-Agent Mapping

| Workflow | Primary Agent | Role |
|----------|---------------|------|
| `new-project.md` | gsd-roadmapper | Creates delivery roadmap after requirements |
| `research-phase.md` | gsd-phase-researcher | Researches domain for specific phase |
| `discuss-phase.md` | (none) | Gathers context via user conversation |
| `plan-phase.md` | gsd-planner | Decomposes phase into executable plans |
| `execute-phase.md` | gsd-executor | Executes plans, writes code, creates files |
| `verify-phase.md` | gsd-verifier | Validates phase against must-haves |
| `debug.md` | gsd-debugger | Diagnoses broken functionality |
| `check-todos.md` | (none) | Lists pending work items |

---

*Structure analysis: 2026-02-18*
