"""Tests for /health and /ready observability endpoints.

Uses FastAPI TestClient with in-memory SQLite connections to verify
liveness and readiness probes without external dependencies.
"""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from negotiation.health import register_health_routes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(services: dict | None = None) -> FastAPI:
    """Create a minimal FastAPI app with health routes and given services."""
    app = FastAPI()
    app.state.services = services or {}
    register_health_routes(app)
    return app


# ---------------------------------------------------------------------------
# /health (liveness)
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /health liveness probe."""

    def test_health_returns_200(self) -> None:
        app = _make_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# /ready (readiness)
# ---------------------------------------------------------------------------

class TestReadyEndpoint:
    """GET /ready readiness probe."""

    def test_ready_returns_200_when_services_ok(self) -> None:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        app = _make_app({"audit_conn": conn, "gmail_client": object()})
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"]["audit_db"] == "ok"
        assert body["checks"]["gmail"] == "ok"

        conn.close()

    def test_ready_returns_503_when_db_missing(self) -> None:
        """audit_conn is None -> audit_db fails."""
        app = _make_app({"audit_conn": None, "gmail_client": object()})
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["audit_db"] == "fail"
        assert body["checks"]["gmail"] == "ok"

    def test_ready_returns_503_when_gmail_missing(self) -> None:
        """gmail_client is None -> gmail fails."""
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        app = _make_app({"audit_conn": conn, "gmail_client": None})
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["audit_db"] == "ok"
        assert body["checks"]["gmail"] == "fail"

        conn.close()

    def test_ready_returns_503_when_both_missing(self) -> None:
        """Both audit_conn and gmail_client unavailable."""
        app = _make_app({"audit_conn": None, "gmail_client": None})
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["audit_db"] == "fail"
        assert body["checks"]["gmail"] == "fail"

    def test_ready_returns_503_when_db_connection_broken(self) -> None:
        """A closed connection that raises on execute -> audit_db fails."""
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.close()  # close so execute raises ProgrammingError
        app = _make_app({"audit_conn": conn, "gmail_client": object()})
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["audit_db"] == "fail"
        assert body["checks"]["gmail"] == "ok"
