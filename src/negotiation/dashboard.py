"""Dashboard module -- serves the React frontend as static files from FastAPI.

When the frontend/dist/ directory exists (production build), mounts:
- Static assets at /dashboard/assets (JS/CSS bundles)
- SPA catch-all at /dashboard and /dashboard/{path} returning index.html

In development, the Vite dev server handles frontend serving directly,
so this module gracefully no-ops when dist/ is absent.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Resolve the frontend dist path relative to this file's location.
# Layout: src/negotiation/dashboard.py -> ../../frontend/dist
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def mount_dashboard(app: FastAPI) -> None:
    """Mount the React dashboard on the FastAPI application.

    If ``frontend/dist/`` exists, serves the built React app at ``/dashboard``.
    Otherwise logs an info message and returns (no-op for dev mode).

    Args:
        app: The FastAPI application instance.
    """
    if not FRONTEND_DIST.is_dir():
        logger.info(
            "Frontend dist/ not found at %s -- dashboard not mounted (dev mode?)",
            FRONTEND_DIST,
        )
        return

    index_html = FRONTEND_DIST / "index.html"
    if not index_html.is_file():
        logger.warning(
            "dist/ exists but index.html missing at %s -- dashboard not mounted",
            index_html,
        )
        return

    # Cache the index.html content so we don't read from disk on every request.
    index_content = index_html.read_text(encoding="utf-8")

    # Mount static assets (JS/CSS bundles produced by Vite).
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/dashboard/assets",
            StaticFiles(directory=str(assets_dir)),
            name="dashboard-assets",
        )

    # SPA fallback: all /dashboard routes return index.html so React Router
    # can handle client-side routing.
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_root() -> HTMLResponse:
        """Serve the React SPA at /dashboard."""
        return HTMLResponse(content=index_content)

    @app.get("/dashboard/{path:path}", response_class=HTMLResponse)
    async def dashboard_spa_fallback(path: str) -> HTMLResponse:
        """Catch-all for /dashboard/* -- returns index.html for SPA routing."""
        return HTMLResponse(content=index_content)

    logger.info("Dashboard mounted at /dashboard (serving from %s)", FRONTEND_DIST)
