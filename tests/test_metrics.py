"""Tests for Prometheus metrics endpoint and custom business metrics."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from negotiation.observability.metrics import (
    ACTIVE_NEGOTIATIONS,
    DEALS_CLOSED,
    setup_metrics,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset custom metric values between tests.

    Prometheus collectors are registered globally, so we reset values rather
    than re-creating them.  The instrumentator registers its collectors once
    and subsequent calls are no-ops (guarded internally).
    """
    ACTIVE_NEGOTIATIONS.set(0)
    # Counter cannot be reset, but we track relative increments in tests
    yield


@pytest.fixture()
def metrics_app() -> FastAPI:
    """Create a minimal FastAPI app with Prometheus instrumentation."""
    app = FastAPI()

    @app.get("/hello")
    async def hello():
        return {"msg": "hello"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    setup_metrics(app)
    return app


@pytest.fixture()
def metrics_client(metrics_app: FastAPI) -> TestClient:
    """TestClient for the metrics-enabled app."""
    return TestClient(metrics_app)


def test_metrics_endpoint_returns_prometheus_format(metrics_client: TestClient) -> None:
    """GET /metrics returns 200 with Prometheus-format text containing expected metrics."""
    # Make a request first so http_request metrics have data
    metrics_client.get("/hello")
    resp = metrics_client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "http_request" in body
    assert "negotiation_active_total" in body
    assert "negotiation_deals_closed_total" in body


def test_excluded_handlers_not_in_metrics(metrics_client: TestClient) -> None:
    """/health and /ready do NOT appear in metrics output (excluded_handlers works)."""
    metrics_client.get("/health")
    metrics_client.get("/ready")
    resp = metrics_client.get("/metrics")
    body = resp.text
    # The excluded_handlers should prevent /health and /ready from showing
    # in http_request_duration_seconds buckets.  We check they do not appear
    # as handler labels in the instrumentator output.
    lines = [
        line
        for line in body.splitlines()
        if "http_request_duration" in line and 'handler="' in line
    ]
    for line in lines:
        assert '/health"' not in line, f"/health found in metrics: {line}"
        assert '/ready"' not in line, f"/ready found in metrics: {line}"


def test_active_negotiations_gauge_changes(metrics_client: TestClient) -> None:
    """ACTIVE_NEGOTIATIONS gauge is reflected in /metrics output."""
    ACTIVE_NEGOTIATIONS.set(5)
    resp = metrics_client.get("/metrics")
    assert "negotiation_active_total 5.0" in resp.text

    ACTIVE_NEGOTIATIONS.set(3)
    resp = metrics_client.get("/metrics")
    assert "negotiation_active_total 3.0" in resp.text


def test_deals_closed_counter_increments(metrics_client: TestClient) -> None:
    """DEALS_CLOSED counter increments are reflected in /metrics output."""
    # Read initial value
    resp = metrics_client.get("/metrics")
    initial_text = resp.text
    # Find the counter value line
    initial_value = _extract_counter_value(initial_text, "negotiation_deals_closed_total")

    DEALS_CLOSED.inc()
    resp = metrics_client.get("/metrics")
    new_value = _extract_counter_value(resp.text, "negotiation_deals_closed_total")
    assert new_value == initial_value + 1.0


def _extract_counter_value(text: str, metric_name: str) -> float:
    """Extract the numeric value of a counter from Prometheus text output."""
    for line in text.splitlines():
        if line.startswith(metric_name) and not line.startswith(metric_name + "_"):
            # e.g. "negotiation_deals_closed_total 3.0"
            parts = line.split()
            if len(parts) == 2:
                return float(parts[1])
    raise ValueError(f"Metric {metric_name} not found in output")
