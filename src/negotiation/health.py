"""Health and readiness endpoints for container orchestration.

Provides two top-level routes:

- ``GET /health`` -- Liveness probe.  Returns 200 if the process is alive.
- ``GET /ready``  -- Readiness probe.  Returns 200 only when the audit DB
  connection is functional **and** the Gmail client is initialized.  Returns
  503 with per-check details otherwise.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register_health_routes(app: FastAPI) -> None:
    """Register ``/health`` and ``/ready`` endpoints on *app*.

    Args:
        app: The FastAPI application instance.
    """

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe -- always returns 200 if the process is running."""
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        """Readiness probe -- checks audit DB and Gmail client availability."""
        services: dict[str, Any] = request.app.state.services
        checks: dict[str, str] = {}

        # Check 1: audit DB connection
        audit_conn = services.get("audit_conn")
        if audit_conn is not None:
            try:
                await asyncio.to_thread(audit_conn.execute, "SELECT 1")
                checks["audit_db"] = "ok"
            except Exception:
                checks["audit_db"] = "fail"
        else:
            checks["audit_db"] = "fail"

        # Check 2: Gmail client initialized
        gmail_client = services.get("gmail_client")
        if gmail_client is not None:
            checks["gmail"] = "ok"
        else:
            checks["gmail"] = "fail"

        all_ok = all(v == "ok" for v in checks.values())
        status = "ready" if all_ok else "not_ready"
        code = 200 if all_ok else 503

        return JSONResponse(content={"status": status, "checks": checks}, status_code=code)
