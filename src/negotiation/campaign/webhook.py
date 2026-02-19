"""FastAPI webhook endpoint for receiving ClickUp campaign form submissions.

Verifies HMAC-SHA256 signatures against raw request body bytes BEFORE JSON
parsing (per research pitfall 4). Only processes ``taskCreated`` events.
Per LOCKED DECISION: one-way data flow only (ClickUp -> agent), no status
sync back.

The ``process_campaign_task`` callback is set at application startup via
``set_campaign_processor`` -- this avoids circular imports and enables
independent testing of the webhook layer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request

logger = structlog.get_logger()

router = APIRouter()

# Module-level callback for campaign processing. Set via set_campaign_processor().
_campaign_processor: Callable[[str], Any] | None = None


def set_campaign_processor(processor: Callable[[str], Any]) -> None:
    """Register the callback invoked when a taskCreated event is received.

    Called at application startup to wire the ingestion pipeline into the
    webhook without a direct import dependency.

    Args:
        processor: A callable that accepts a ClickUp task_id string.
    """
    global _campaign_processor
    _campaign_processor = processor


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of a webhook payload.

    CRITICAL: Must be called with raw body bytes BEFORE any JSON parsing
    to ensure the signature matches the exact bytes sent by ClickUp.

    Args:
        body: The raw request body bytes.
        signature: The HMAC-SHA256 hex digest from the X-Signature header.
        secret: The webhook signing secret from CLICKUP_WEBHOOK_SECRET.

    Returns:
        True if the computed signature matches the provided one.
    """
    computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("/webhooks/clickup")
async def clickup_webhook(request: Request) -> dict[str, str]:
    """Receive and process ClickUp webhook events.

    1. Read raw body bytes (before JSON parsing).
    2. Verify HMAC-SHA256 signature from X-Signature header.
    3. Parse JSON only after signature verification.
    4. Process only ``taskCreated`` events by delegating to the campaign processor.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A status dict indicating success.

    Raises:
        HTTPException: 401 if signature is missing or invalid.
    """
    secret = request.app.state.settings.clickup_webhook_secret
    if not secret:
        logger.error("CLICKUP_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    # Step 1: Read raw body bytes BEFORE parsing
    raw_body = await request.body()

    # Step 2: Get and verify signature
    signature = request.headers.get("X-Signature")
    if not signature:
        logger.warning("Missing X-Signature header in webhook request")
        raise HTTPException(status_code=401, detail="Missing signature")

    if not verify_signature(raw_body, signature, secret):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Step 3: Parse JSON AFTER signature verification
    payload: dict[str, Any] = json.loads(raw_body)

    # Step 4: Only process taskCreated events
    event = payload.get("event")
    if event != "taskCreated":
        logger.info("Ignoring non-taskCreated event", event_type=event)
        return {"status": "ok"}

    task_id = payload.get("task_id", "")
    if not task_id:
        logger.warning("taskCreated event missing task_id")
        return {"status": "ok"}

    logger.info("Processing taskCreated event", task_id=task_id)

    if _campaign_processor is not None:
        _campaign_processor(task_id)
    else:
        logger.warning("No campaign processor registered; skipping task", task_id=task_id)

    return {"status": "ok"}


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        A status dict indicating the service is healthy.
    """
    return {"status": "healthy"}
