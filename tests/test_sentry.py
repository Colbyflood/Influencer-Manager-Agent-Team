"""Tests for Sentry SDK initialization and structlog-sentry bridge."""

from __future__ import annotations

from unittest.mock import patch

from negotiation.observability.sentry import get_sentry_processor, init_sentry


def test_init_sentry_noop_with_empty_dsn() -> None:
    """init_sentry('') does not raise and does not call sentry_sdk.init."""
    with patch("negotiation.observability.sentry.sentry_sdk.init") as mock_init:
        init_sentry("")
        mock_init.assert_not_called()


def test_init_sentry_calls_sdk_with_dsn() -> None:
    """init_sentry with a DSN calls sentry_sdk.init with correct parameters."""
    test_dsn = "https://examplePublicKey@o0.ingest.sentry.io/0"
    with patch("negotiation.observability.sentry.sentry_sdk.init") as mock_init:
        init_sentry(test_dsn)
        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args
        assert call_kwargs.kwargs["dsn"] == test_dsn
        assert call_kwargs.kwargs["send_default_pii"] is False
        assert call_kwargs.kwargs["traces_sample_rate"] == 0.1


def test_get_sentry_processor_returns_callable() -> None:
    """get_sentry_processor() returns a callable (SentryProcessor instance)."""
    processor = get_sentry_processor()
    assert callable(processor)
