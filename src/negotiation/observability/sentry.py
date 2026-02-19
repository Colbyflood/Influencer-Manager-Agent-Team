"""Sentry SDK initialization with structlog-sentry bridge.

Provides:
- ``init_sentry(dsn)``: Initialize Sentry SDK.  No-op when *dsn* is empty.
- ``get_sentry_processor()``: Return a structlog processor that forwards
  ERROR-level log events to Sentry.
"""

from __future__ import annotations

import logging

import sentry_sdk
import structlog
from sentry_sdk.integrations.logging import LoggingIntegration
from structlog_sentry import SentryProcessor


def init_sentry(dsn: str) -> None:
    """Initialize Sentry SDK with the given *dsn*.

    When *dsn* is empty the function returns immediately -- no network calls,
    no SDK initialization.  Safe to call unconditionally at startup.

    Args:
        dsn: Sentry DSN string.  Empty string disables Sentry.
    """
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
        integrations=[
            # Disable Sentry's default logging capture to prevent
            # double-reporting with structlog-sentry.
            LoggingIntegration(event_level=None, level=None),
        ],
    )


def get_sentry_processor() -> structlog.types.Processor:
    """Return a structlog processor that forwards ERROR events to Sentry.

    Insert this into the structlog processor chain **after** ``add_log_level``
    and **before** the renderer (``TimeStamper``).

    Returns:
        A ``SentryProcessor`` instance configured for ERROR-level capture.
    """
    return SentryProcessor(event_level=logging.ERROR)
