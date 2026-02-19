# ============================================================================
# BUILD STAGE -- install dependencies with uv
# ============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies only (cached unless pyproject.toml or uv.lock changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy entire project
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# ============================================================================
# RUNTIME STAGE -- slim image with non-root user
# ============================================================================
FROM python:3.12-slim-bookworm

# Create non-root system user (UID/GID 999)
RUN groupadd --system --gid 999 appuser \
 && useradd --system --gid 999 --uid 999 --no-create-home --shell /usr/sbin/nologin appuser

# Create data directory with correct ownership (inherited by new named volumes)
RUN mkdir -p /app/data/credentials \
 && chown -R appuser:appuser /app/data

# Copy application from builder with appuser ownership
COPY --from=builder --chown=appuser:appuser /app /app

# Copy entrypoint as root-owned (it runs as root to do chown)
COPY --chown=root:root entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy config and knowledge_base directories (needed at runtime)
COPY --chown=appuser:appuser config/ /app/config/
COPY --chown=appuser:appuser knowledge_base/ /app/knowledge_base/

# Set PATH to include venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# HEALTHCHECK with self-kill pattern for auto-restart
# Uses Python urllib (no curl in slim image). The || kill 1 sends SIGTERM
# to PID 1 if health check fails 3 consecutive times, causing container exit.
# Combined with restart: unless-stopped in docker-compose.yml, this achieves
# auto-restart on health failure.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || kill 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "negotiation.app"]
