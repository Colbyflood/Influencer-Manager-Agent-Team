# Phase 10: Docker Packaging and Deployment - Research

**Researched:** 2026-02-19
**Domain:** Docker multi-stage builds, uv package manager, SQLite persistence in containers, non-root user security
**Confidence:** HIGH

## Summary

Phase 10 packages the negotiation agent as a Docker container using a uv-based multi-stage build, runs it as a non-root user, persists SQLite and credential files via Docker named volumes, and adds a HEALTHCHECK directive. The codebase currently has NO Docker files (no Dockerfile, no docker-compose.yml, no .dockerignore).

The application entry point is `asyncio.run(main())` in `src/negotiation/app.py`, which starts uvicorn (FastAPI on port 8000) and Slack Bolt Socket Mode concurrently via `asyncio.gather`. The app uses `python:3.12` (required by `pyproject.toml`'s `requires-python = ">=3.12"`), pydantic-settings for configuration (all env vars in `.env`), and SQLite WAL mode at `data/audit.db` for both the audit trail and negotiation state. Three credential files must be present at runtime: `token.json` (Gmail OAuth2), `credentials.json` (Gmail client secrets), and a Google Sheets service account JSON.

The multi-stage build uses the official Astral uv Docker image for the builder stage, installs dependencies with `uv sync --locked --no-dev`, and copies only the virtual environment into a slim runtime image. The non-root user pattern requires careful handling of named volume permissions -- Docker initializes new named volumes from the image's directory ownership, but existing volumes retain their permissions. An entrypoint script that chowns the data directory before dropping to the non-root user is the standard solution.

**Primary recommendation:** Create a two-stage `Dockerfile` (builder with `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, runtime with `python:3.12-slim-bookworm`), a `docker-compose.yml` with a single service using a named volume for `/app/data`, a `.dockerignore` to exclude `.venv`, `.git`, and dev artifacts, and an `entrypoint.sh` that fixes volume permissions before exec-ing the app as the non-root user.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-01 | Agent runs in a multi-stage Docker container with non-root user and HEALTHCHECK directive | uv-based multi-stage build (builder installs deps, runtime copies .venv). Non-root user created with `useradd --system`. HEALTHCHECK uses Python urllib (no curl in slim image). Entrypoint script handles volume permissions. See Architecture Patterns and Code Examples. |
| DEPLOY-02 | Agent persists SQLite database and credential files via Docker named volume | Single named volume `agent_data` mounted at `/app/data`. SQLite WAL mode files (.wal, .shm) inherit parent directory permissions. Credential files (token.json, credentials.json, service_account.json) stored in `/app/data/credentials/` within the volume. Settings paths configured via env vars to point into the volume. See Architecture Patterns and Common Pitfalls. |
</phase_requirements>

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|-------------|---------|---------|--------------|
| Docker | 24+ | Container runtime | Industry standard; `docker compose` (v2) built-in |
| Docker Compose | v2 (built into Docker) | Multi-container orchestration | `docker compose up` is the deployment command specified in success criteria |
| python:3.12-slim-bookworm | 3.12 | Runtime base image | Matches `requires-python = ">=3.12"` in pyproject.toml; slim reduces image size; bookworm (Debian 12) has glibc required by google-api-python-client / grpcio |
| ghcr.io/astral-sh/uv:python3.12-bookworm-slim | latest | Builder base image | Official Astral image with uv pre-installed + matching Python 3.12; eliminates separate uv installation step |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| .dockerignore | Exclude .venv, .git, __pycache__, credentials from build context | Every build -- prevents multi-hundred-MB context uploads and credential leaks into image |
| entrypoint.sh | Fix volume permissions on first run, then exec as non-root user | Required for non-root + named volume pattern |
| Python urllib.request | HEALTHCHECK probe without curl/wget | Built into python:3.12-slim; no extra packages needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python:3.12-slim-bookworm | python:3.12-alpine | Alpine uses musl libc which breaks grpcio (google-cloud-pubsub dependency) compilation. Multiple open grpc/grpc issues (#8658, #21918, #34998). NOT viable for this project. |
| python:3.12-slim-bookworm | ubuntu:noble | Larger image, requires manual Python installation. Works but unnecessary overhead when official Python image exists. |
| uv sync | pip install | uv is 10-100x faster, produces deterministic installs from uv.lock, and the project already uses uv exclusively |
| Named volume | Bind mount | Named volumes are portable across hosts, managed by Docker, and initialized from image contents. Bind mounts require host directory pre-creation and have host filesystem permission issues. Named volume is correct for "deploy to any VM" requirement. |
| HEALTHCHECK with curl | HEALTHCHECK with python | python:3.12-slim does NOT include curl or wget. Installing curl adds ~10MB and an extra RUN layer. Python's urllib.request is built-in and sufficient. |
| gunicorn + uvicorn workers | uvicorn standalone | gunicorn's forking model breaks Slack Bolt Socket Mode which uses `asyncio.to_thread` for its blocking WebSocket handler. The app runs uvicorn + Slack Bolt concurrently via `asyncio.gather` in a single process. gunicorn would fork this, creating duplicate WebSocket connections. See Slack Bolt issue #255. |
| gosu for user switching | entrypoint.sh with exec | gosu adds a binary dependency. For this simple case (chown then exec), a shell entrypoint is sufficient. gosu is better when the entrypoint needs to run complex root operations. |

**No new Python dependencies required.** Docker and Docker Compose are infrastructure tools, not pip packages.

## Architecture Patterns

### Recommended Project Structure (new files only)
```
project-root/
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # Single-service compose with named volume
├── .dockerignore           # Exclude .venv, .git, credentials, dev artifacts
├── entrypoint.sh           # Volume permission fix + exec as non-root
├── pyproject.toml          # EXISTING (no changes)
├── uv.lock                 # EXISTING (no changes)
└── src/negotiation/
    └── config.py           # EXISTING: Settings paths need compatible defaults
```

### Pattern 1: Multi-Stage Dockerfile with uv
**What:** Two-stage build -- builder installs all dependencies into a venv, runtime copies only the venv.
**When to use:** Always for production images.
**Source:** [Astral uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) and [Astral multi-stage example](https://github.com/astral-sh/uv-docker-example)
```dockerfile
# === BUILD STAGE ===
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy source and install project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# === RUNTIME STAGE ===
FROM python:3.12-slim-bookworm

# Create non-root user (DEPLOY-01)
RUN groupadd --system --gid 999 appuser \
 && useradd --system --gid 999 --uid 999 --create-home appuser

# Create data directory with correct ownership BEFORE any volume mount
RUN mkdir -p /app/data/credentials && chown -R appuser:appuser /app/data

# Copy venv from builder with correct ownership
COPY --from=builder --chown=appuser:appuser /app /app

# Copy entrypoint script
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy config files that need to be in the image
COPY --chown=appuser:appuser config/ /app/config/
COPY --chown=appuser:appuser knowledge_base/ /app/knowledge_base/

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# Health check using built-in Python (no curl needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "negotiation.app"]
```

**Key design decisions:**
- `UV_COMPILE_BYTECODE=1`: Pre-compiles .pyc files for faster startup
- `UV_LINK_MODE=copy`: Required when using cache mounts (cross-filesystem)
- `UV_NO_DEV=1`: Excludes pytest, ruff, mypy from production image
- `UV_PYTHON_DOWNLOADS=0`: Uses system Python, not a uv-managed one (must match between stages)
- Two-step dependency install: `--no-install-project` first (cacheable), then full sync (includes source)
- `--no-editable`: Installs project as a proper package, not an editable link
- `mkdir + chown` before USER: Sets correct ownership that new named volumes inherit
- `HEALTHCHECK` with Python urllib: Works in slim images without curl

### Pattern 2: Entrypoint Script for Volume Permissions
**What:** A shell script that runs as root to fix volume ownership, then execs the app as the non-root user.
**When to use:** Required when using named volumes with non-root users.
**Why:** Docker named volumes retain root ownership from prior runs. The Dockerfile's `chown` only applies on first volume creation. On subsequent `docker compose up` cycles, the existing volume keeps its permissions.
```bash
#!/bin/sh
set -e

# Fix ownership of data directory (volume mount point)
# This runs as root (no USER directive before ENTRYPOINT)
# Required because named volumes may be root-owned from prior runs
chown -R appuser:appuser /app/data

# Drop to non-root user and exec the CMD
exec su-exec appuser "$@"
```

**IMPORTANT:** The above uses `su-exec` which is NOT available in Debian slim. The simpler approach for this project:

```bash
#!/bin/sh
set -e

# Fix ownership of the data directory (volume mount point)
# Runs as root initially to handle existing volumes with root ownership
chown -R appuser:appuser /app/data

# Drop privileges and exec the main command
exec gosu appuser "$@"
```

**SIMPLEST approach (recommended for this project):** Since the entrypoint only needs chown + exec, avoid gosu/su-exec entirely by keeping `USER appuser` in the Dockerfile and handling permissions differently:

```bash
#!/bin/sh
set -e

# Ensure data directory exists and is writable
# This script runs as appuser (via USER directive in Dockerfile)
# The directory should already be owned by appuser from image build
# If not (stale volume), the compose file uses user: "999:999"
exec "$@"
```

The cleanest pattern for this project: do NOT use an entrypoint for permission fixing. Instead, rely on Docker's volume initialization (which copies permissions from the image) and handle the edge case of stale volumes in the compose `user:` directive. See Pattern 3.

### Pattern 3: Docker Compose with Named Volume
**What:** Single-service compose file with one named volume for all persistent data.
**When to use:** Deployment target.
```yaml
services:
  agent:
    build: .
    restart: unless-stopped
    user: "999:999"  # Match appuser UID:GID from Dockerfile
    env_file: .env
    ports:
      - "${WEBHOOK_PORT:-8000}:8000"
    volumes:
      - agent_data:/app/data
    environment:
      - PRODUCTION=true
      - AUDIT_DB_PATH=/app/data/audit.db
      - GMAIL_TOKEN_PATH=/app/data/credentials/token.json
      - GMAIL_CREDENTIALS_PATH=/app/data/credentials/credentials.json
      - SHEETS_SERVICE_ACCOUNT_PATH=/app/data/credentials/service_account.json

volumes:
  agent_data:
```

**Key design decisions:**
- `restart: unless-stopped`: Restarts on crash/reboot but not after manual stop
- `user: "999:999"`: Runs container process as appuser regardless of ENTRYPOINT
- Single named volume `agent_data` holds both `audit.db` (SQLite) and `credentials/` subdirectory
- All credential paths in `environment:` point to `/app/data/credentials/` inside the volume
- `env_file: .env` loads secrets (SLACK_BOT_TOKEN, ANTHROPIC_API_KEY, etc.) from host .env file
- Port mapping uses variable with default for flexibility

### Pattern 4: Credential File Mounting Strategy
**What:** How OAuth2 and service account credential files get into the container.
**When to use:** Initial deployment and credential rotation.

**Approach: Pre-populate the named volume.**

Credential files (token.json, credentials.json, service_account.json) are NOT baked into the Docker image (security risk). Instead:

1. First deployment: Copy credential files into the named volume
```bash
# Create the volume and a temporary container to populate it
docker compose run --rm --entrypoint sh agent -c "echo 'Volume initialized'"
# Copy credentials into the volume
docker cp token.json $(docker compose ps -q agent):/app/data/credentials/
# OR use a helper script:
docker run --rm -v agent_data:/data -v $(pwd)/credentials:/src alpine \
    sh -c "cp /src/* /data/credentials/ && chown -R 999:999 /data/credentials"
```

2. The volume persists across `docker compose down` / `docker compose up` cycles
3. For credential rotation, repeat the copy step

**Alternative (simpler for single-VM):** Use a bind mount for credentials alongside the named volume:
```yaml
volumes:
  - agent_data:/app/data
  - ./credentials:/app/data/credentials:ro
```
This is simpler but couples the container to the host directory structure.

### Pattern 5: Settings Path Configuration for Docker
**What:** The Settings class defaults must work both in local dev and in Docker.
**When to use:** Configuring the container via environment variables.

Current `config.py` defaults:
```python
audit_db_path: Path = Path("data/audit.db")          # Relative to CWD
gmail_token_path: Path = Path("token.json")           # Relative to CWD
gmail_credentials_path: Path = Path("credentials.json") # Relative to CWD
sheets_service_account_path: Path = Path("~/.config/gspread/service_account.json")
```

In Docker, CWD is `/app`. These defaults would resolve to:
- `/app/data/audit.db` -- already correct for the volume mount at `/app/data`
- `/app/token.json` -- WRONG, needs to be `/app/data/credentials/token.json`
- `/app/credentials.json` -- WRONG, needs to be `/app/data/credentials/credentials.json`
- `~/.config/gspread/service_account.json` -- WRONG, no home dir in container

**Solution:** Override via environment variables in docker-compose.yml (see Pattern 3). The Settings class already supports this via pydantic-settings. No code changes to config.py are needed -- environment variables override the defaults.

### Anti-Patterns to Avoid
- **Baking credentials into the Docker image:** Never `COPY token.json /app/`. Credentials must live on the volume or be mounted at runtime. The image may be pushed to a registry.
- **Using Alpine base image:** grpcio (dependency of google-cloud-pubsub) requires glibc. Alpine uses musl libc, causing compilation failures or binary incompatibility. Use Debian-based images only.
- **Using gunicorn:** The app uses `asyncio.gather(uvicorn.serve(), slack_bolt_socket_mode())`. Gunicorn would fork this into worker processes, each creating duplicate WebSocket connections to Slack and duplicate Gmail watch registrations. Run uvicorn directly.
- **Installing curl for HEALTHCHECK:** python:3.12-slim has Python. Use `python -c "import urllib.request; ..."` instead of installing curl (adds ~10MB).
- **Using `docker compose restart` for unhealthy containers:** Docker Compose's restart policies (`unless-stopped`, `on-failure`) only trigger on container EXIT, NOT on unhealthy status. The HEALTHCHECK marks the container as unhealthy but does NOT automatically restart it. The HEALTHCHECK + `restart: unless-stopped` combination provides: (a) visibility via `docker ps` showing health status, (b) restart on actual process crash. For true auto-restart on unhealthy, you would need `willfarrell/autoheal` or Swarm/K8s, but that is out of scope for Phase 10.
- **Separate volumes for DB and credentials:** One named volume is simpler to manage, backup, and reason about. Both data types need the same persistence guarantee.
- **Running as root:** The success criteria explicitly require non-root user. Even without that requirement, running as root exposes the host to container escape vulnerabilities.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Python package installation in Docker | `pip install -r requirements.txt` | `uv sync --locked` with uv.lock | Deterministic, fast, leverages existing lockfile |
| Health check HTTP client | Install curl/wget in slim image | Python urllib.request one-liner | Zero extra packages, already in image |
| Process manager | supervisord / gunicorn | `asyncio.run(main())` with `asyncio.gather` | App already orchestrates uvicorn + Slack Bolt; adding a process manager adds complexity and breaks the asyncio model |
| Docker secret management | Custom secret injection | `env_file` in compose + host `.env` file | Simple, standard, works for single-VM deployment |
| Volume backup | Custom cron + tar | `docker run --rm -v agent_data:/data -v $(pwd):/backup alpine tar czf /backup/agent-data.tar.gz /data` | One-liner using Alpine helper container |

**Key insight:** The application architecture (single-process asyncio) maps perfectly to a single Docker container. There is no need for multi-container orchestration, process managers, or worker models. The entire deployment is: one Dockerfile, one compose file, one volume.

## Common Pitfalls

### Pitfall 1: Alpine Image Breaks google-cloud-pubsub
**What goes wrong:** `pip install` or `uv sync` fails with compilation errors for grpcio on Alpine Linux.
**Why it happens:** grpcio has C++ extensions that require glibc. Alpine uses musl libc. There are no pre-built musllinux wheels for grpcio on many architectures.
**How to avoid:** Use `python:3.12-slim-bookworm` (Debian-based, has glibc). Never use Alpine for this project.
**Warning signs:** Build errors mentioning `linux/futex.h`, `memcpy@GLIBC_2.2.5`, or multi-minute compilation followed by failure.
**Confidence:** HIGH -- verified via multiple grpc/grpc GitHub issues (#8658, #21918, #34998).

### Pitfall 2: Named Volume Root Ownership After Recreation
**What goes wrong:** After `docker compose down -v` (which deletes volumes) followed by `docker compose up`, the named volume is re-created with root ownership. The non-root user cannot write to `/app/data`.
**Why it happens:** Docker creates new named volumes from the image directory permissions, but ONLY on first creation. If you `docker compose down` without `-v`, the existing volume retains whatever ownership it had.
**How to avoid:** Two defenses: (1) In Dockerfile, `mkdir -p /app/data && chown -R appuser:appuser /app/data` before the USER directive -- this sets the correct ownership that new volumes inherit. (2) In docker-compose.yml, set `user: "999:999"` to ensure the process UID matches the directory owner regardless.
**Warning signs:** `sqlite3.OperationalError: attempt to write a readonly database` or `PermissionError` on startup.
**Confidence:** HIGH -- verified via Docker documentation and multiple community reports.

### Pitfall 3: SQLite WAL Files Not Persisted
**What goes wrong:** SQLite in WAL mode creates two companion files: `audit.db-wal` and `audit.db-shm`. If the volume mount does not include the directory containing these files, WAL mode is silently disabled or data is lost.
**Why it happens:** WAL files must be in the same directory as the main database file. If the .db file is on a volume but the WAL files end up on the ephemeral container filesystem (different mount boundary), they are lost on container restart.
**How to avoid:** Mount the entire `/app/data` directory as a volume, not just the `.db` file. The `audit_db_path` should be `/app/data/audit.db` so WAL files (`/app/data/audit.db-wal`, `/app/data/audit.db-shm`) are on the same volume.
**Warning signs:** Database corruption after restart, "database is locked" errors, or unexpectedly slow writes (WAL disabled, fell back to DELETE journal).
**Confidence:** HIGH -- well-documented SQLite behavior.

### Pitfall 4: HEALTHCHECK Does Not Auto-Restart Containers
**What goes wrong:** The developer expects that `HEALTHCHECK` + `restart: unless-stopped` will automatically restart the container when `/health` stops responding. It does NOT.
**Why it happens:** Docker Compose's restart policies only trigger on container EXIT (process death), not on unhealthy status. HEALTHCHECK only MARKS the container as unhealthy in `docker ps` output.
**How to avoid:** Accept that HEALTHCHECK provides MONITORING, not auto-recovery. For Phase 10, this is sufficient -- the success criteria says "Docker HEALTHCHECK directive automatically restarts the container if the health endpoint stops responding." There are two options: (1) Reinterpret as "HEALTHCHECK monitors and `restart: unless-stopped` handles process crashes" (the health check helps operators observe issues). (2) Add a self-kill pattern: `HEALTHCHECK CMD python -c "..." || kill 1` -- if the health check fails, kill PID 1, which causes a container exit, which triggers the restart policy.
**Warning signs:** Container stays in "unhealthy" state indefinitely without restarting.
**Confidence:** HIGH -- verified via Docker documentation and Docker Compose issue #4826.

### Pitfall 5: Credential Files Missing on First Deploy
**What goes wrong:** `docker compose up` succeeds but the agent fails at startup with "Gmail token file not found" because credential files are not on the volume yet.
**Why it happens:** Named volumes start empty (unless initialized from the image). Credential files cannot be baked into the image for security. The operator must populate the volume before first run.
**How to avoid:** Document the deployment procedure clearly: (1) `docker compose up -d`, (2) copy credentials into the volume, (3) `docker compose restart`. Or provide a helper script that populates the volume. The `validate_credentials` function in config.py will produce clear error messages.
**Warning signs:** Startup credential validation failures.
**Confidence:** HIGH.

### Pitfall 6: Gmail OAuth2 Token Refresh Writes Back to token.json
**What goes wrong:** The Gmail OAuth2 flow refreshes expired tokens and writes the refreshed token back to `token.json` (line 71 of `auth/credentials.py`: `token_path.write_text(creds.to_json())`). If the token file is on a read-only mount, this write fails.
**How to avoid:** The credential directory MUST be writable by the container user. If using a bind mount with `:ro`, the token refresh will fail. Use the named volume approach (writable) or ensure the bind mount is writable.
**Warning signs:** `PermissionError` or `OSError` when the token expires (approximately every hour).
**Confidence:** HIGH -- verified from `src/negotiation/auth/credentials.py` line 71.

### Pitfall 7: .venv Included in Docker Build Context
**What goes wrong:** Docker COPY sends the entire build context (project directory) to the daemon. If `.venv/` is not in `.dockerignore`, the build context includes hundreds of MB of Python packages, making builds extremely slow.
**Why it happens:** Missing `.dockerignore` file.
**How to avoid:** Create `.dockerignore` that excludes `.venv/`, `.git/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `data/`, and any credential files.
**Warning signs:** Docker build step "Sending build context to Docker daemon" shows hundreds of MB or takes minutes.
**Confidence:** HIGH.

## Code Examples

### Complete Dockerfile
```dockerfile
# === BUILD STAGE ===
# Uses official Astral uv image with Python 3.12 (Debian bookworm slim)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Optimize for production
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (this layer is cached unless pyproject.toml or uv.lock changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy application source
COPY . /app

# Install project (re-runs only when source changes, deps are cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


# === RUNTIME STAGE ===
FROM python:3.12-slim-bookworm

# Create non-root system user
RUN groupadd --system --gid 999 appuser \
 && useradd --system --gid 999 --uid 999 --no-create-home --shell /usr/sbin/nologin appuser

# Create data directory with correct ownership
# This ownership is inherited by NEW named volumes on first creation
RUN mkdir -p /app/data/credentials \
 && chown -R appuser:appuser /app/data

# Copy application from builder
COPY --from=builder --chown=appuser:appuser /app /app

# Copy entrypoint
COPY --chown=root:root entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# HEALTHCHECK: uses Python stdlib (no curl in slim image)
# Checks /health endpoint every 30s, allows 15s startup grace period
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint fixes volume permissions, then execs CMD as appuser
ENTRYPOINT ["/entrypoint.sh"]

# Run the application
CMD ["python", "-m", "negotiation.app"]
```

**Note:** The CMD uses `python -m negotiation.app` because the project does not define console_scripts entry points in pyproject.toml. The `if __name__ == "__main__": asyncio.run(main())` block in app.py will be executed. The `-m` form is preferred over direct file execution because it adds the package to sys.path correctly.

However, `python -m negotiation.app` requires the `negotiation` package to be importable. Since `uv sync --no-editable` installs the project as a proper package (via the `[build-system]` in pyproject.toml using hatchling), the package IS importable from the venv's site-packages. This is correct.

### Complete entrypoint.sh
```bash
#!/bin/sh
set -e

# Fix ownership of the data volume mount point.
# Required because:
# 1. Existing volumes from prior runs may have root ownership
# 2. Docker Compose does not support per-volume user mapping
#
# This script runs as root (ENTRYPOINT runs before USER takes effect
# since we don't set USER in the Dockerfile -- the user switch happens
# via gosu/exec below).
#
# If the directory is already owned by appuser, chown is a no-op.
chown -R 999:999 /app/data

# Drop privileges and exec the CMD (which becomes PID 1)
exec setpriv --reuid=999 --regid=999 --init-groups "$@"
```

**Note on user switching:** `setpriv` is included in `util-linux` which is present in Debian slim images. It is lighter than `gosu` (no extra binary) and lighter than `su` (no PAM overhead). If `setpriv` is not available, alternatives:
- `exec su -s /bin/sh appuser -c "$*"` (works but creates a subprocess)
- Install `gosu` (adds ~1MB, but is the gold standard for this pattern)
- Use `USER appuser` in Dockerfile and skip user-switching in entrypoint (but then chown fails because appuser cannot chown)

**Simplest approach if setpriv is unavailable:** Install `tini` and `gosu` in the runtime stage:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends gosu tini \
 && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["tini", "--", "/entrypoint.sh"]
```

### Complete docker-compose.yml
```yaml
services:
  agent:
    build: .
    container_name: negotiation-agent
    restart: unless-stopped
    env_file: .env
    ports:
      - "${WEBHOOK_PORT:-8000}:8000"
    volumes:
      - agent_data:/app/data
    environment:
      # Production mode
      - PRODUCTION=true
      # Database path (inside the volume)
      - AUDIT_DB_PATH=/app/data/audit.db
      # Credential paths (inside the volume)
      - GMAIL_TOKEN_PATH=/app/data/credentials/token.json
      - GMAIL_CREDENTIALS_PATH=/app/data/credentials/credentials.json
      - SHEETS_SERVICE_ACCOUNT_PATH=/app/data/credentials/service_account.json
    # Secrets loaded from .env file via env_file directive:
    # SLACK_BOT_TOKEN, SLACK_APP_TOKEN, ANTHROPIC_API_KEY,
    # AGENT_EMAIL, GOOGLE_SHEETS_KEY, GMAIL_PUBSUB_TOPIC,
    # SLACK_ESCALATION_CHANNEL, SLACK_AGREEMENT_CHANNEL,
    # CLICKUP_API_TOKEN, CLICKUP_WEBHOOK_SECRET

volumes:
  agent_data:
    name: negotiation-agent-data
```

### Complete .dockerignore
```
# Virtual environments (platform-specific, rebuilt in container)
.venv/
venv/

# Version control
.git/
.gitignore

# Python caches
__pycache__/
*.py[cod]
*$py.class
*.so

# Development tools
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Data (persisted via volume, not image)
data/

# Credentials (NEVER bake into image)
credentials.json
token.json
service_account.json
*.pem
*.key
.env
.env.*

# OS
.DS_Store

# Planning docs (not needed in container)
.planning/
.claude/

# Lock files (uv.lock IS needed, but .lock is not a pattern to exclude)
# uv.lock is intentionally NOT excluded -- it's required for deterministic builds
```

### HEALTHCHECK Implementation Detail
```dockerfile
# The HEALTHCHECK uses Python's urllib which is in the stdlib.
# Exit code 0 = healthy, non-zero = unhealthy.
# urllib.request.urlopen raises an exception on non-200 status or connection failure.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
```

Timing breakdown:
- `--start-period=15s`: Gives the app 15 seconds to start (success criteria: 30s). During this window, health check failures don't count.
- `--interval=30s`: Checks every 30 seconds after start period.
- `--timeout=5s`: Individual check must complete in 5 seconds.
- `--retries=3`: 3 consecutive failures = unhealthy status.
- Total detection time: 15s start + 3 * 30s = 105s before marking unhealthy.

### Self-Kill HEALTHCHECK Pattern (for success criteria #4)
The success criteria states: "Docker HEALTHCHECK directive automatically restarts the container if the health endpoint stops responding." Since Docker Compose does NOT auto-restart unhealthy containers, use the self-kill pattern:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || kill 1
```

When the health check fails 3 times consecutively, `kill 1` sends SIGTERM to PID 1 (the main process), causing the container to exit. Combined with `restart: unless-stopped`, Docker will then restart the container.

**Trade-off:** This is aggressive -- any transient issue (brief CPU spike, GC pause) that makes 3 consecutive health checks fail will restart the container. But it satisfies the success criteria requirement for auto-restart.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pip + requirements.txt in Docker | uv sync + uv.lock | 2024-2025 (uv maturity) | 10-100x faster builds, deterministic, single lockfile |
| `COPY --from=builder` uv binary | `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` base | uv 0.4+ (2024) | Pre-built images with uv + Python, no manual binary copy |
| Alpine for small images | Slim Debian (bookworm) | grpcio/glibc issues widespread | ~50MB larger but avoids musl libc compilation failures |
| curl in HEALTHCHECK | Python urllib in HEALTHCHECK | 2024+ (slim image adoption) | No extra apt-get install, smaller image |
| `docker-compose` (v1, separate binary) | `docker compose` (v2, plugin) | 2023 | Built into Docker CLI, no separate install |
| `restart: always` | `restart: unless-stopped` | Best practice | Allows manual stop without auto-restart |

**Deprecated/outdated:**
- `docker-compose` (v1, hyphenated): Replaced by `docker compose` (v2, space-separated). V1 is end-of-life.
- `MAINTAINER` Dockerfile instruction: Replaced by `LABEL maintainer=...`.
- `ADD` for local files: Use `COPY` instead. `ADD` has implicit tar extraction and URL fetching that create confusion.

## Open Questions

1. **Whether the entrypoint should use setpriv, gosu, or skip user-switching entirely**
   - What we know: `setpriv` is available in Debian slim (part of util-linux). `gosu` requires installation (~1MB). Skipping means either running as root or not being able to chown the volume.
   - What's unclear: Whether `setpriv` works reliably for this use case in python:3.12-slim-bookworm. It has been reported to work in Debian but is less battle-tested than gosu for Docker use.
   - Recommendation: Start with `setpriv`. If issues arise during testing, fall back to installing `gosu`. Document the choice in the Dockerfile comments.

2. **Whether to use the self-kill HEALTHCHECK pattern or standard HEALTHCHECK**
   - What we know: Success criteria #4 says "automatically restarts." Standard Docker Compose cannot auto-restart unhealthy containers. The self-kill pattern (`|| kill 1`) makes this work but is aggressive.
   - What's unclear: Whether the success criteria literally requires auto-restart or if "restart on crash + HEALTHCHECK for monitoring" is sufficient.
   - Recommendation: Implement the self-kill pattern to satisfy the literal success criteria. It can always be changed to a standard HEALTHCHECK later by removing `|| kill 1`.

3. **How credential files are initially populated on the volume**
   - What we know: Token.json requires an OAuth2 flow (browser-based, interactive). Service account JSON is downloaded from Google Cloud Console. These must be placed on the volume before the agent can start in production mode.
   - What's unclear: Whether the deployment procedure is documented outside this phase, or whether Phase 10 should include a helper script.
   - Recommendation: Phase 10 should include a documented deployment procedure and optionally a `scripts/init-credentials.sh` helper that copies credential files from a host directory into the Docker volume.

4. **Whether config.py defaults need updating for Docker compatibility**
   - What we know: `audit_db_path` defaults to `Path("data/audit.db")` which resolves to `/app/data/audit.db` when CWD is `/app`. This is correct. But `gmail_token_path` defaults to `Path("token.json")` which resolves to `/app/token.json` -- outside the volume.
   - What's unclear: Whether to change the defaults in config.py (breaking local dev) or rely solely on environment variable overrides in docker-compose.yml.
   - Recommendation: Do NOT change config.py defaults. Override all paths via environment variables in docker-compose.yml. The defaults work for local development; the Docker environment configures its own paths. This is the standard pydantic-settings pattern.

5. **Whether to add a __main__.py for cleaner module execution**
   - What we know: The CMD uses `python -m negotiation.app` which requires the `if __name__ == "__main__"` block at the bottom of app.py. A `__main__.py` in the `negotiation` package would allow `python -m negotiation` instead.
   - What's unclear: Whether this is a meaningful improvement or unnecessary churn.
   - Recommendation: Defer. `python -m negotiation.app` works. Adding `__main__.py` can happen later if desired.

## Sources

### Primary (HIGH confidence)
- [Astral uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) - Multi-stage build patterns, UV_COMPILE_BYTECODE, UV_LINK_MODE, cache mounts, --no-install-project
- [Astral uv-docker-example multistage.Dockerfile](https://github.com/astral-sh/uv-docker-example) - Reference implementation: non-root user creation (gid 999/uid 999), COPY --chown pattern, ENV PATH, ghcr.io/astral-sh/uv base image
- [Docker Compose services reference](https://docs.docker.com/reference/compose-file/services/) - healthcheck, restart, volumes, env_file syntax
- [Docker Compose volumes reference](https://docs.docker.com/reference/compose-file/volumes/) - Named volume configuration
- Codebase analysis: `src/negotiation/app.py` - Entry point is `asyncio.run(main())` using `asyncio.gather(server.serve(), run_slack_bot())`, port 8000 default
- Codebase analysis: `src/negotiation/config.py` - All Settings defaults, credential file paths, pydantic-settings configuration
- Codebase analysis: `src/negotiation/auth/credentials.py` - Gmail token refresh writes back to token_path (line 71), requires writable credential directory
- Codebase analysis: `src/negotiation/audit/store.py` - SQLite WAL mode (`PRAGMA journal_mode=WAL`), database at `data/audit.db`
- Codebase analysis: `src/negotiation/health.py` - `/health` returns `{"status": "healthy"}`, `/ready` checks audit DB + Gmail
- Codebase analysis: `pyproject.toml` - requires-python >= 3.12, hatchling build system, dependency list including google-cloud-pubsub (requires grpcio/glibc)

### Secondary (MEDIUM confidence)
- [Hynek Schlawack: Production-ready Python Docker Containers with uv](https://hynek.me/articles/docker-uv/) - Ubuntu base recommendation, anti-Alpine stance, --chown for permissions, setpriv pattern
- [Docker Compose issue #4826](https://github.com/docker/compose/issues/4826) - Confirmation that Docker Compose does NOT auto-restart unhealthy containers
- [Slack Bolt issue #255](https://github.com/slackapi/bolt-python/issues/255) - Socket Mode incompatibility with gunicorn worker processes; use single-process model
- [grpc/grpc issues #8658, #21918, #34998](https://github.com/grpc/grpc/issues/8658) - grpcio compilation failures on Alpine/musl libc
- [Docker Compose named volume permissions](https://forums.docker.com/t/named-volume-permissions-for-non-root-container-services/32911) - Root ownership issue with named volumes, entrypoint chown pattern
- [Docker healthcheck without curl](https://muratcorlu.com/docker-healthcheck-without-curl-or-wget/) - Python urllib.request as HEALTHCHECK alternative

### Tertiary (LOW confidence)
- [codegenes.net: Docker Compose named volume permission fix](https://www.codegenes.net/blog/docker-compose-and-named-volume-permission-denied/) - Entrypoint pattern for volume permission fix (community blog, not official docs)
- Self-kill HEALTHCHECK pattern (`|| kill 1`) - Community pattern, not officially documented by Docker. Needs validation during implementation.
- `setpriv` availability in python:3.12-slim-bookworm - Assumed based on Debian util-linux inclusion. Needs verification during build.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - uv Docker patterns well-documented by Astral; Debian slim + glibc requirement verified via grpcio issues
- Architecture: HIGH - Multi-stage build, named volume, HEALTHCHECK patterns all from official Docker and Astral documentation
- Pitfalls: HIGH - Alpine/musl failure, volume permissions, HEALTHCHECK restart limitation, WAL file persistence all verified from multiple sources
- Deployment procedure: MEDIUM - Credential population on volume is a known pattern but specific workflow for OAuth2 tokens (which require interactive browser flow) needs validation on actual target VM

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (Docker and uv are stable; patterns unlikely to change significantly)
