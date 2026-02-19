"""Wrapper functions that add audit logging around existing pipeline operations.

Each ``create_audited_*`` function accepts an original callable and an
:class:`AuditLogger`, returning a new callable that delegates to the original
AND logs the action.  This avoids modifying the original modules while
achieving comprehensive logging at every pipeline integration point.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from negotiation.audit.logger import AuditLogger


def create_audited_email_send(
    original_send: Callable[..., Any],
    audit_logger: AuditLogger,
) -> Callable[..., Any]:
    """Return a wrapper that calls *original_send* and logs via audit trail.

    The wrapper expects keyword arguments matching the email send interface:
    ``influencer_name``, ``thread_id``, ``email_body``, ``negotiation_state``,
    ``rates_used``, and optionally ``campaign_id``.

    Args:
        original_send: The original email-send callable.
        audit_logger: The audit logger instance.

    Returns:
        A wrapped callable with identical signature and return value.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = original_send(*args, **kwargs)
        audit_logger.log_email_sent(
            campaign_id=kwargs.get("campaign_id"),
            influencer_name=kwargs.get("influencer_name", ""),
            thread_id=kwargs.get("thread_id", ""),
            email_body=kwargs.get("email_body", ""),
            negotiation_state=kwargs.get("negotiation_state", ""),
            rates_used=kwargs.get("rates_used"),
        )
        return result

    return wrapper


def create_audited_email_receive(
    original_receive: Callable[..., Any],
    audit_logger: AuditLogger,
) -> Callable[..., Any]:
    """Return a wrapper that calls *original_receive* and logs via audit trail.

    The wrapper expects keyword arguments: ``influencer_name``, ``thread_id``,
    ``email_body``, ``negotiation_state``, ``intent_classification``, and
    optionally ``campaign_id``.

    Args:
        original_receive: The original email-receive callable.
        audit_logger: The audit logger instance.

    Returns:
        A wrapped callable with identical signature and return value.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = original_receive(*args, **kwargs)
        audit_logger.log_email_received(
            campaign_id=kwargs.get("campaign_id"),
            influencer_name=kwargs.get("influencer_name", ""),
            thread_id=kwargs.get("thread_id", ""),
            email_body=kwargs.get("email_body", ""),
            negotiation_state=kwargs.get("negotiation_state", ""),
            intent_classification=kwargs.get("intent_classification"),
        )
        return result

    return wrapper


def create_audited_process_reply(
    original_process: Callable[..., dict[str, Any]],
    audit_logger: AuditLogger,
) -> Callable[..., dict[str, Any]]:
    """Return a wrapper around ``process_influencer_reply`` with audit logging.

    After calling the original function, inspects the returned action dict
    and logs the appropriate event:

    - ``action="send"`` -- :meth:`AuditLogger.log_email_sent`
    - ``action="escalate"`` -- :meth:`AuditLogger.log_escalation`
    - ``action="accept"`` -- :meth:`AuditLogger.log_agreement`
    - ``action="reject"`` -- :meth:`AuditLogger.log_state_transition`

    Args:
        original_process: The original ``process_influencer_reply`` callable.
        audit_logger: The audit logger instance.

    Returns:
        A wrapped callable that returns the original action dict unchanged.
    """

    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result: dict[str, Any] = original_process(*args, **kwargs)
        action = result.get("action", "")

        # Extract context from kwargs or positional args
        negotiation_context: dict[str, Any] = {}
        if len(args) >= 2:
            negotiation_context = args[1] if isinstance(args[1], dict) else {}
        negotiation_context = kwargs.get("negotiation_context", negotiation_context)

        campaign_id = negotiation_context.get("campaign_id")
        influencer_name = str(negotiation_context.get("influencer_name", ""))
        thread_id = str(negotiation_context.get("thread_id", ""))
        negotiation_state = str(negotiation_context.get("negotiation_state", ""))

        if action == "send":
            audit_logger.log_email_sent(
                campaign_id=campaign_id,
                influencer_name=influencer_name,
                thread_id=thread_id,
                email_body=result.get("email_body", ""),
                negotiation_state=negotiation_state,
                rates_used=str(result.get("our_rate", "")),
            )
        elif action == "escalate":
            audit_logger.log_escalation(
                campaign_id=campaign_id,
                influencer_name=influencer_name,
                thread_id=thread_id,
                reason=result.get("reason", ""),
                negotiation_state=negotiation_state,
            )
        elif action == "accept":
            classification = result.get("classification")
            agreed_rate = ""
            if classification and hasattr(classification, "proposed_rate"):
                agreed_rate = str(classification.proposed_rate or "")
            audit_logger.log_agreement(
                campaign_id=campaign_id,
                influencer_name=influencer_name,
                thread_id=thread_id,
                agreed_rate=agreed_rate,
                negotiation_state=negotiation_state,
            )
        elif action == "reject":
            audit_logger.log_state_transition(
                campaign_id=campaign_id,
                influencer_name=influencer_name,
                thread_id=thread_id,
                from_state=negotiation_state,
                to_state="rejected",
                event="reject",
            )

        return result

    return wrapper


def wire_audit_to_campaign_ingestion(
    ingest_fn: Callable[..., Any],
    audit_logger: AuditLogger,
) -> Callable[..., Any]:
    """Return a wrapper around ``ingest_campaign`` with audit logging.

    After calling the original function, logs:

    - :meth:`AuditLogger.log_campaign_start` with influencer counts
    - :meth:`AuditLogger.log_campaign_influencer_skip` for each missing influencer

    Args:
        ingest_fn: The original ``ingest_campaign`` callable.
        audit_logger: The audit logger instance.

    Returns:
        A wrapped callable that returns the original result unchanged.
    """

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await ingest_fn(*args, **kwargs)

        campaign = result.get("campaign")
        campaign_id = campaign.campaign_id if campaign else kwargs.get("task_id", "unknown")
        found = result.get("found_influencers", [])
        missing = result.get("missing_influencers", [])
        total = len(found) + len(missing)

        audit_logger.log_campaign_start(
            campaign_id=str(campaign_id),
            influencer_count=total,
            found_count=len(found),
            missing_count=len(missing),
        )

        for name in missing:
            audit_logger.log_campaign_influencer_skip(
                campaign_id=str(campaign_id),
                influencer_name=name,
                reason="Not found in Google Sheet",
            )

        return result

    return wrapper


def wire_audit_to_dispatcher(
    dispatcher: Any,
    audit_logger: AuditLogger,
) -> None:
    """Wrap ``SlackDispatcher`` methods to add audit logging.

    Patches ``dispatch_escalation``, ``dispatch_agreement``, and
    ``pre_check`` (for human takeover detection) to log via the
    audit trail.  Uses the wrapper pattern: stores the original method
    and creates a new one that calls original + logs.

    Args:
        dispatcher: A ``SlackDispatcher`` instance.
        audit_logger: The audit logger instance.
    """
    original_dispatch_escalation = dispatcher.dispatch_escalation
    original_dispatch_agreement = dispatcher.dispatch_agreement
    original_pre_check = dispatcher.pre_check

    def audited_dispatch_escalation(payload: Any) -> str:
        result: str = original_dispatch_escalation(payload)
        audit_logger.log_escalation(
            campaign_id=getattr(payload, "campaign_id", None),
            influencer_name=getattr(payload, "influencer_name", ""),
            thread_id=getattr(payload, "thread_id", None),
            reason=getattr(payload, "reason", ""),
            negotiation_state="escalated",
        )
        return result

    def audited_dispatch_agreement(payload: Any) -> str:
        result: str = original_dispatch_agreement(payload)
        audit_logger.log_agreement(
            campaign_id=getattr(payload, "campaign_id", None),
            influencer_name=getattr(payload, "influencer_name", ""),
            thread_id=getattr(payload, "thread_id", None),
            agreed_rate=str(getattr(payload, "agreed_rate", "")),
            negotiation_state="agreed",
        )
        return result

    def audited_pre_check(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
        result: dict[str, Any] | None = original_pre_check(*args, **kwargs)
        is_human_skip = (
            result
            and result.get("action") == "skip"
            and "human" in result.get("reason", "").lower()
        )
        if is_human_skip:
            thread_id = kwargs.get("thread_id", args[1] if len(args) > 1 else "")
            audit_logger.log_takeover(
                campaign_id=None,
                influencer_name="",
                thread_id=str(thread_id),
                taken_by="auto-detected",
            )
        return result

    dispatcher.dispatch_escalation = audited_dispatch_escalation
    dispatcher.dispatch_agreement = audited_dispatch_agreement
    dispatcher.pre_check = audited_pre_check
