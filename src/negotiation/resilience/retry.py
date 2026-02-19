"""Resilient API call decorator with tenacity retry and Slack error notification.

Per locked decision: Retry 3 times with exponential backoff and jitter,
then post error to Slack #errors channel on final failure.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from tenacity import (
    RetryCallState,
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = structlog.get_logger()

# Module-level notifier for error reporting (avoids circular import with SlackNotifier)
_notifier: Any = None

F = TypeVar("F", bound=Callable[..., Any])


def configure_error_notifier(notifier: Any) -> None:
    """Set the module-level notifier for error reporting.

    Call this at application startup with your SlackNotifier instance
    to enable Slack error notifications on final retry failure.

    Args:
        notifier: An object with a post_escalation(blocks, fallback_text) method,
                  typically a SlackNotifier instance.
    """
    global _notifier
    _notifier = notifier


def notify_slack_on_final_failure(retry_state: RetryCallState) -> None:
    """Log failure and post to Slack #errors channel on final retry exhaustion.

    Args:
        retry_state: Tenacity retry state with attempt info and exception.
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    api_name = retry_state.kwargs.get("api_name", "unknown")

    logger.error(
        "API call failed after all retries",
        api_name=api_name,
        attempts=retry_state.attempt_number,
        exception=str(exception),
    )

    if _notifier is not None:
        try:
            _notifier.post_escalation(
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*API Error: {api_name}*\n"
                                f"Failed after {retry_state.attempt_number} attempts.\n"
                                f"Error: `{exception}`"
                            ),
                        },
                    }
                ],
                fallback_text=f"API Error: {api_name} failed after retries",
            )
        except Exception:
            logger.exception("Failed to send Slack error notification")


def _before_sleep_log(retry_state: RetryCallState) -> None:
    """Log a warning before each retry attempt.

    Args:
        retry_state: Tenacity retry state with attempt info.
    """
    api_name = getattr(retry_state.fn, "_api_name", "unknown") if retry_state.fn else "unknown"
    logger.warning(
        "Retrying API call",
        api_name=api_name,
        attempt=retry_state.attempt_number,
        wait=retry_state.next_action.sleep if retry_state.next_action else 0,
    )


def resilient_api_call(api_name: str) -> Callable[[F], F]:
    """Create a retry decorator for an API call.

    Returns a tenacity retry decorator configured with:
    - 3 attempts maximum
    - Exponential backoff with jitter (1s initial, 30s max, 5s jitter)
    - Warning log before each retry
    - Slack error notification on final failure
    - Original exception re-raised after exhaustion

    Args:
        api_name: Human-readable name for the API (used in logs and alerts).

    Returns:
        A decorator that wraps the function with retry logic.
    """

    def decorator(func: F) -> F:
        # Store api_name on function for before_sleep_log access
        func._api_name = api_name  # type: ignore[attr-defined]

        wrapped = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
            before_sleep=_before_sleep_log,
            retry_error_callback=notify_slack_on_final_failure,
            reraise=True,
        )(func)

        return wrapped

    return decorator
