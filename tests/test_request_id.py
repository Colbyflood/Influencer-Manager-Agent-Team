"""Tests for Request ID middleware."""

from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from negotiation.observability.middleware import RequestIdMiddleware

UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with RequestIdMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


def test_response_has_auto_generated_request_id() -> None:
    """When no X-Request-ID header is sent, response has an auto-generated UUID."""
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.status_code == 200
    request_id = resp.headers.get("X-Request-ID", "")
    assert request_id, "X-Request-ID header should be present"
    assert UUID4_PATTERN.match(request_id), f"Expected UUID4 format, got: {request_id}"


def test_response_echoes_client_request_id() -> None:
    """When client sends X-Request-ID, response echoes the same value."""
    client = TestClient(_make_app())
    resp = client.get("/test", headers={"X-Request-ID": "test-123"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "test-123"
