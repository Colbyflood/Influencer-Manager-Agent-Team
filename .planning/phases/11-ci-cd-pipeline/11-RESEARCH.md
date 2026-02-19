# Phase 11: CI/CD Pipeline - Research

**Researched:** 2026-02-19
**Domain:** GitHub Actions CI, Python linting (ruff), type checking (mypy), testing (pytest), uv package manager in CI
**Confidence:** HIGH

## Summary

Phase 11 adds a GitHub Actions CI workflow that runs ruff lint, mypy typecheck, and pytest on every push and pull request. The project already has all three tools configured in `pyproject.toml` and all existing tests are fully isolated (using mocks and in-memory SQLite -- no external services required). The project uses `uv` as its package manager with a `uv.lock` lockfile, and the official `astral-sh/setup-uv@v7` action provides fast, cached dependency installation in CI.

The implementation is straightforward: a single `.github/workflows/ci.yml` file with three parallel jobs (lint, typecheck, test) that each use `astral-sh/setup-uv@v7` with caching enabled. The workflow triggers on `push` (all branches) and `pull_request` events. Branch protection rules on `main` then require the CI workflow jobs to pass before a PR can be merged. The existing test suite (50+ test files across 11 test directories) already runs in isolation without any external dependencies.

**Primary recommendation:** Create `.github/workflows/ci.yml` with three parallel jobs (ruff, mypy, pytest) using `astral-sh/setup-uv@v7` for dependency management, then configure GitHub branch protection on `main` to require all three status checks to pass.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-03 | GitHub Actions CI runs ruff lint, mypy typecheck, and pytest on every push | Single workflow file `.github/workflows/ci.yml` triggered on `push` and `pull_request`. Three parallel jobs use `astral-sh/setup-uv@v7` for fast cached setup. `uv run ruff check --output-format=github .` for lint, `uv run mypy src/` for typecheck, `uv run pytest` for tests. All tools already configured in `pyproject.toml`. Branch protection enforces checks on PRs. See Architecture Patterns and Code Examples. |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| GitHub Actions | v2 (YAML workflows) | CI/CD platform | Native GitHub integration; free for public repos, generous free tier for private |
| astral-sh/setup-uv | v7 | Install uv + cache dependencies in CI | Official Astral action; handles caching via `uv.lock` hash; installs Python version from `.python-version` |
| actions/checkout | v6 | Check out repository code | Standard first step in every GitHub Actions workflow |
| ruff | >=0.15 (from pyproject.toml dev deps) | Linting and format checking | Already configured in `[tool.ruff]`; supports `--output-format=github` for inline PR annotations |
| mypy | >=1.19 (from pyproject.toml dev deps) | Static type checking | Already configured in `[tool.mypy]` with strict mode, pydantic plugin |
| pytest | >=9.0,<10 (from pyproject.toml dev deps) | Test runner | Already configured in `[tool.pytest.ini_options]` with testpaths, pythonpath, addopts |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| pytest-cov | Coverage reporting | Already in dev deps; use `--cov=src/negotiation` flag to generate coverage data |
| GitHub branch protection rules | Enforce CI passes before merge | Configure after first workflow run on `main` branch |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single workflow with 3 jobs | Separate workflow files per tool | Single file is simpler; separate files allow independent re-runs but add maintenance overhead. Single file is standard for small-medium projects. |
| astral-sh/setup-uv | pip install from requirements.txt | uv is 10-100x faster, project already uses uv exclusively with uv.lock, no requirements.txt exists |
| Branch protection rules (classic) | Repository rulesets (new) | Rulesets are newer and more powerful (stackable, visible to non-admins) but branch protection rules are simpler, well-documented, and sufficient for a single-repo team. Either works. |
| Three parallel jobs | Single sequential job | Parallel jobs give granular failure reporting (know exactly which check failed from PR status) and run faster. Slight overhead of 3x checkout+setup but uv caching makes this fast (~10s setup per job). |

**Installation:**
No package installation needed. The workflow file references existing `pyproject.toml` dev dependencies via `uv sync --locked --dev`.

## Architecture Patterns

### Recommended Project Structure
```
.github/
└── workflows/
    └── ci.yml              # Single CI workflow file
.python-version             # Already exists: "3.12"
pyproject.toml              # Already has [tool.ruff], [tool.mypy], [tool.pytest.ini_options]
uv.lock                     # Already exists: lockfile for deterministic installs
```

### Pattern 1: Parallel CI Jobs with Shared Setup
**What:** A single workflow with three independent jobs (lint, typecheck, test) that run in parallel. Each job checks out code, installs uv + dependencies, then runs one tool.
**When to use:** When you have multiple independent checks that should all pass before merge.
**Example:**
```yaml
# Source: https://docs.astral.sh/uv/guides/integration/github/
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --locked --dev
      - run: uv run ruff check --output-format=github .

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --locked --dev
      - run: uv run mypy src/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --locked --dev
      - run: uv run pytest
```

### Pattern 2: Trigger on Push to All Branches + Pull Requests
**What:** Workflow triggers on `push` (all branches, not just main) and `pull_request` events so CI runs on every commit regardless of workflow.
**When to use:** When the success criteria require "pushing a commit to any branch triggers the workflow."
**Why both triggers:** `push` catches direct pushes to any branch. `pull_request` catches PR creation/updates and is required for branch protection status checks to appear on PRs.
**Example:**
```yaml
on:
  push:             # Every push to every branch
  pull_request:     # Every PR update
```

Note: When both trigger on the same commit (e.g., pushing to a PR branch), GitHub Actions runs the workflow twice. This is standard behavior and harmless -- the branch protection check only requires the `pull_request`-triggered run to pass.

### Pattern 3: Branch Protection Required Status Checks
**What:** Configure GitHub branch protection on `main` to require specific CI job names to pass before PR merge is allowed.
**When to use:** After the workflow has run at least once on the repository (GitHub only shows checks that have previously run).
**How:**
1. Push the workflow file to `main` (or a branch and merge it)
2. Go to Settings > Branches > Add rule (or edit existing)
3. Branch name pattern: `main`
4. Enable "Require status checks to pass before merging"
5. Search for and select: `lint`, `typecheck`, `test` (the job names from the workflow)
6. Optionally enable "Require branches to be up to date before merging"

**Important:** Job names in the workflow become the status check names. Keep them short and descriptive. If you rename a job, you must update the branch protection rule.

### Anti-Patterns to Avoid
- **Triggering only on `pull_request`:** Direct pushes to `main` (or any branch without a PR) would skip CI entirely. The success criteria require "any branch" triggers.
- **Running all checks in a single job:** Hides which specific check failed. With parallel jobs, the PR status shows exactly which check (lint/typecheck/test) failed.
- **Using `pip install` in CI when the project uses uv:** Creates a divergence between local dev and CI environments. The lockfile (`uv.lock`) ensures deterministic installs only when using `uv sync --locked`.
- **Hardcoding Python version in the workflow:** The project has a `.python-version` file. `astral-sh/setup-uv@v7` reads it automatically via `uv python install`, keeping the version in one place.
- **Using `uv sync` without `--locked`:** Without `--locked`, uv may update dependencies. `--locked` ensures the lockfile is respected exactly, failing if it's stale. This catches developers who forget to update `uv.lock`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Python + dependency setup in CI | Manual `pip install`, `python -m venv`, custom caching | `astral-sh/setup-uv@v7` with `enable-cache: true` | Handles uv installation, Python version detection from `.python-version`, cache invalidation via `uv.lock` hash. 10-100x faster than pip. |
| Lint PR annotations | Custom regex parsing of ruff output | `ruff check --output-format=github` | Native GitHub Actions annotation format. Shows lint errors inline on PR diffs. |
| mypy PR annotations | Custom problem matcher JSON files | `astral-sh/setup-uv@v7` with `add-problem-matchers: true` (enabled by default) | The setup-uv action registers problem matchers automatically. mypy's default output format is already parseable by GitHub's built-in Python problem matcher. |
| Branch protection enforcement | Custom scripts to block merges | GitHub branch protection rules | Native GitHub feature. UI-configurable, no code required. |
| Cache invalidation | Manual cache key management | `cache-dependency-glob: "uv.lock"` in setup-uv | Automatic cache invalidation when `uv.lock` changes. No manual `hashFiles()` calls needed. |

**Key insight:** The entire CI pipeline for this project requires exactly ONE new file (`.github/workflows/ci.yml`). All tool configuration already exists in `pyproject.toml`, the lockfile exists, and `.python-version` specifies the runtime. The workflow is pure orchestration -- it just invokes existing tools.

## Common Pitfalls

### Pitfall 1: Status Checks Not Appearing in Branch Protection
**What goes wrong:** After creating the workflow, the job names don't appear in the branch protection "required status checks" dropdown.
**Why it happens:** GitHub only populates the dropdown with checks that have actually run on the repository. If the workflow has never run on `main` (or any branch), the checks don't exist yet.
**How to avoid:** Push the workflow file to `main` first (or merge a PR that adds it), then configure branch protection. The workflow must run at least once for the check names to appear.
**Warning signs:** Empty search results when typing job names in branch protection settings.

### Pitfall 2: Stale uv.lock Fails CI
**What goes wrong:** `uv sync --locked` fails with an error about the lockfile being out of date.
**Why it happens:** A developer added/changed a dependency in `pyproject.toml` but forgot to run `uv lock` to update `uv.lock`.
**How to avoid:** This is actually the desired behavior -- `--locked` deliberately fails when the lockfile is stale. The fix is to run `uv lock` locally and commit the updated `uv.lock`. This is a feature, not a bug.
**Warning signs:** CI fails on `uv sync --locked` step with "lockfile is not up-to-date" error.

### Pitfall 3: .env File Leaking Into CI Tests
**What goes wrong:** Tests behave differently in CI vs locally because a local `.env` file sets variables that affect Settings defaults.
**Why it happens:** `pydantic-settings` loads `.env` files by default. Locally, developers may have a `.env` file with real credentials.
**How to avoid:** The existing test pattern already handles this correctly: tests pass `_env_file=None` when constructing Settings directly, or construct Settings objects explicitly with test values. CI has no `.env` file, so `Settings()` uses defaults (production=False, empty strings for secrets). The existing tests are already CI-safe.
**Warning signs:** Tests pass locally but fail in CI (or vice versa) due to different environment variables.

### Pitfall 4: Duplicate Workflow Runs on PR Pushes
**What goes wrong:** Both `push` and `pull_request` triggers fire when pushing to a PR branch, causing two workflow runs per push.
**Why it happens:** GitHub Actions fires `push` for the branch push and `pull_request` for the PR update.
**How to avoid:** This is harmless -- both runs are independent and the branch protection check uses the `pull_request`-triggered run. To reduce runner minutes, you could limit `push` to `branches: [main]` only, but this would violate the success criteria that "pushing a commit to any branch triggers the workflow." Accept the duplicate runs as acceptable overhead.
**Warning signs:** Two CI runs appear for each push to a PR branch. This is expected behavior.

### Pitfall 5: mypy Fails on Missing Type Stubs
**What goes wrong:** mypy reports errors about missing type stubs for third-party packages.
**Why it happens:** Some packages (e.g., `slack_bolt`, `gspread`) don't ship py.typed markers or inline stubs.
**How to avoid:** The project already has `google-api-python-client-stubs` in dev deps and uses `mypy --strict`. If mypy currently passes locally, it will pass in CI because `uv sync --locked --dev` installs the exact same dependencies. The `[[tool.mypy.overrides]]` section already relaxes rules for `tests.*`.
**Warning signs:** mypy errors about import-untyped that don't appear locally. Check that dev dependencies are fully installed.

## Code Examples

Verified patterns from official sources:

### Complete CI Workflow File
```yaml
# Source: https://docs.astral.sh/uv/guides/integration/github/
# Adapted for this project's specific tools and configuration
name: CI

on:
  push:
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - name: Install dependencies
        run: uv sync --locked --dev
      - name: Ruff lint
        run: uv run ruff check --output-format=github .
      - name: Ruff format check
        run: uv run ruff format --check .

  typecheck:
    name: typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - name: Install dependencies
        run: uv sync --locked --dev
      - name: Mypy
        run: uv run mypy src/

  test:
    name: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - name: Install dependencies
        run: uv sync --locked --dev
      - name: Pytest
        run: uv run pytest --cov=src/negotiation
```

### Concurrency Control
```yaml
# Source: https://docs.github.com/en/actions/writing-workflows
# Cancel in-progress runs when a new push arrives on the same branch
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
This prevents wasted runner minutes when developers push multiple commits in quick succession.

### Python Version Resolution
```yaml
# setup-uv reads .python-version file automatically
# No explicit python-version needed in the action config
- uses: astral-sh/setup-uv@v7
# uv sync will use Python 3.12 (from .python-version)
- run: uv sync --locked --dev
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install -r requirements.txt` | `uv sync --locked --dev` | 2024 (uv 0.1+) | 10-100x faster installs, deterministic lockfile |
| `actions/setup-python` + manual venv | `astral-sh/setup-uv@v7` (handles Python + deps) | 2024-2025 (setup-uv v1-v7) | Single action replaces setup-python + pip + cache configuration |
| Custom ruff GitHub Action (`astral-sh/ruff-action`) | `uv run ruff check --output-format=github` | 2024+ | Direct invocation is simpler, ruff-action is still maintained but unnecessary when uv is already set up |
| Separate `flake8` + `isort` + `black` | `ruff` (replaces all three) | 2023-2024 | Already done in this project |
| Branch protection rules (classic) | Repository rulesets | 2023-2024 | Rulesets are newer, more powerful; classic branch protection still fully supported and simpler for single-repo |

**Deprecated/outdated:**
- `astral-sh/setup-uv@v5`: Still referenced in some blog posts; current is `v7`
- `actions/checkout@v4`: Current is `v6` (as shown in official uv docs)
- Custom problem matcher JSON files for mypy: `setup-uv` registers Python problem matchers automatically

## Open Questions

1. **Ruff format check: include or exclude?**
   - What we know: `ruff format --check` verifies code formatting without modifying files. The project has `[tool.ruff.format]` configured.
   - What's unclear: Whether the codebase is currently fully formatted according to ruff's rules. If not, the first CI run will fail.
   - Recommendation: Include `ruff format --check` in the lint job. If it fails, run `ruff format .` locally once to fix all formatting, then it stays clean going forward. LOW risk.

2. **Coverage threshold: enforce or report only?**
   - What we know: `pytest-cov` is in dev deps. We can add `--cov-fail-under=N` to enforce a minimum.
   - What's unclear: Current coverage percentage is unknown.
   - Recommendation: Start with `--cov=src/negotiation` (report only, no threshold). Add a threshold later once baseline coverage is known. This is a Phase 12 or later concern.

3. **Branch protection: classic rules or rulesets?**
   - What we know: Both work. Rulesets are newer (2023+), support stacking, visible to non-admins. Classic branch protection is simpler, well-documented.
   - What's unclear: Whether the repository is on GitHub Free or a paid plan (rulesets for private repos require paid plans).
   - Recommendation: Use classic branch protection rules. Simpler, universally available, sufficient for this use case. Document the manual setup steps.

## Sources

### Primary (HIGH confidence)
- [Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/) - Official Astral documentation for CI setup, workflow examples, caching
- [astral-sh/setup-uv README](https://github.com/astral-sh/setup-uv) - v7 action configuration, all input/output parameters, caching options
- [Ruff Integrations](https://docs.astral.sh/ruff/integrations/) - `--output-format=github` for inline PR annotations
- Project `pyproject.toml` - Existing tool configuration for ruff, mypy, pytest
- Project `tests/` directory - 50+ test files, all using mocks/in-memory SQLite, no external dependencies

### Secondary (MEDIUM confidence)
- [A GitHub Actions setup for Python projects in 2025](https://ber2.github.io/posts/2025_github_actions_python/) - Verified patterns for parallel CI jobs with uv
- [GitHub Docs: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) - Branch protection rule configuration
- [GitHub Docs: Required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks) - Troubleshooting check visibility
- [GitHub Docs: About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) - Comparison of rulesets vs classic branch protection

### Tertiary (LOW confidence)
- None. All findings verified against official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Astral docs and GitHub docs confirm all tool versions and configuration
- Architecture: HIGH - The pattern (parallel jobs, uv caching, branch protection) is well-established and documented by official sources
- Pitfalls: HIGH - Based on observed project code (Settings defaults, test isolation patterns) and official GitHub docs (status check visibility requirements)

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable domain; GitHub Actions and uv are mature tools)
