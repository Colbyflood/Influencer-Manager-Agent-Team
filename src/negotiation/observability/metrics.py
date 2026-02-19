"""Prometheus metrics instrumentation for the negotiation agent.

Provides:
- ``setup_metrics(app)``: Attach prometheus-fastapi-instrumentator to a FastAPI app,
  exposing ``/metrics`` with HTTP request duration/count plus custom business gauges.
- ``ACTIVE_NEGOTIATIONS``: Gauge tracking in-memory active negotiation count.
- ``DEALS_CLOSED``: Counter tracking total negotiations reaching AGREED state.

Business metrics are updated at state transitions (not by polling the database).
"""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

ACTIVE_NEGOTIATIONS: Gauge = Gauge(
    "negotiation_active_total",
    "Number of currently active (non-terminal) negotiations",
)

DEALS_CLOSED: Counter = Counter(
    "negotiation_deals_closed_total",
    "Total number of negotiations reaching AGREED state",
)


def setup_metrics(app: FastAPI) -> None:
    """Instrument *app* with Prometheus HTTP metrics and expose ``/metrics``.

    Excludes health/ready/metrics endpoints from instrumentation to avoid
    noise in dashboards.

    Args:
        app: The FastAPI application to instrument.
    """
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/ready", "/metrics"],
    ).instrument(app).expose(app, include_in_schema=False, should_gzip=True)
