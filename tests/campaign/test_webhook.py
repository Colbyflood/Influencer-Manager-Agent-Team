"""Tests for the ClickUp webhook endpoint with HMAC-SHA256 verification.

Covers signature validation, event filtering, callback dispatch, and health
check endpoint.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from negotiation.campaign.webhook import router, set_campaign_processor, verify_signature
from negotiation.config import Settings

# Test webhook secret
TEST_SECRET = "test-webhook-secret-12345"

# Create a minimal FastAPI app wrapping the router for TestClient usage
app = FastAPI()
app.include_router(router)
app.state.settings = Settings(clickup_webhook_secret=TEST_SECRET)  # type: ignore[call-arg]


def _sign(body: bytes, secret: str = TEST_SECRET) -> str:
    """Compute HMAC-SHA256 hex digest for a request body."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_payload(event: str = "taskCreated", task_id: str = "task_abc123") -> dict[str, Any]:
    """Build a ClickUp webhook payload dict."""
    return {"event": event, "task_id": task_id}


@pytest.fixture()
def mock_processor() -> MagicMock:
    """Create and register a mock campaign processor callback."""
    processor = MagicMock()
    set_campaign_processor(processor)
    yield processor
    # Clean up: reset to None after test
    set_campaign_processor(None)  # type: ignore[arg-type]


@pytest.fixture()
def client(mock_processor: MagicMock) -> TestClient:
    """Create a test client with settings configured."""
    yield TestClient(app)  # type: ignore[misc]


# --- verify_signature unit tests ---


class TestVerifySignature:
    """Tests for the HMAC-SHA256 verify_signature function."""

    def test_valid_signature_passes(self) -> None:
        body = b'{"event": "taskCreated"}'
        sig = _sign(body)
        assert verify_signature(body, sig, TEST_SECRET) is True

    def test_invalid_signature_fails(self) -> None:
        body = b'{"event": "taskCreated"}'
        assert verify_signature(body, "bad-signature", TEST_SECRET) is False

    def test_wrong_secret_fails(self) -> None:
        body = b'{"event": "taskCreated"}'
        sig = _sign(body, "wrong-secret")
        assert verify_signature(body, sig, TEST_SECRET) is False

    def test_empty_body_valid_signature(self) -> None:
        body = b""
        sig = _sign(body)
        assert verify_signature(body, sig, TEST_SECRET) is True

    def test_signature_computed_on_raw_bytes(self) -> None:
        """Verify that signature is based on raw bytes, not parsed/re-serialized JSON."""
        # JSON with specific whitespace formatting
        body = b'{"event":   "taskCreated",  "task_id":"abc"}'
        sig = _sign(body)
        assert verify_signature(body, sig, TEST_SECRET) is True

        # Re-serialized version has different bytes -> different signature
        re_serialized = json.dumps(json.loads(body)).encode()
        assert verify_signature(re_serialized, sig, TEST_SECRET) is False


# --- Endpoint tests ---


class TestClickUpWebhookEndpoint:
    """Tests for the /webhooks/clickup endpoint."""

    def test_valid_signature_returns_200(
        self,
        client: TestClient,
        mock_processor: MagicMock,
    ) -> None:
        payload = _make_payload()
        body = json.dumps(payload).encode()
        sig = _sign(body)

        response = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_processor.assert_called_once_with("task_abc123")

    def test_missing_signature_returns_401(self, client: TestClient) -> None:
        payload = _make_payload()
        body = json.dumps(payload).encode()

        response = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401
        assert "Missing signature" in response.json()["detail"]

    def test_invalid_signature_returns_401(self, client: TestClient) -> None:
        payload = _make_payload()
        body = json.dumps(payload).encode()

        response = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"X-Signature": "invalid-sig", "Content-Type": "application/json"},
        )

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_non_task_created_event_returns_200_no_processing(
        self,
        client: TestClient,
        mock_processor: MagicMock,
    ) -> None:
        """Non-taskCreated events are acknowledged but not processed."""
        payload = _make_payload(event="taskUpdated")
        body = json.dumps(payload).encode()
        sig = _sign(body)

        response = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_processor.assert_not_called()

    def test_task_created_event_calls_processor_with_task_id(
        self,
        client: TestClient,
        mock_processor: MagicMock,
    ) -> None:
        """taskCreated event triggers the campaign processor with correct task_id."""
        payload = _make_payload(event="taskCreated", task_id="task_xyz")
        body = json.dumps(payload).encode()
        sig = _sign(body)

        response = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_processor.assert_called_once_with("task_xyz")

    def test_task_created_missing_task_id_returns_200_no_processing(
        self,
        client: TestClient,
        mock_processor: MagicMock,
    ) -> None:
        """taskCreated without task_id is acknowledged but processor is not called."""
        payload: dict[str, str] = {"event": "taskCreated"}
        body = json.dumps(payload).encode()
        sig = _sign(body)

        response = client.post(
            "/webhooks/clickup",
            content=body,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_processor.assert_not_called()

    def test_missing_webhook_secret_returns_500(self) -> None:
        """If clickup_webhook_secret is empty in Settings, return 500."""
        no_secret_app = FastAPI()
        no_secret_app.include_router(router)
        no_secret_app.state.settings = Settings(clickup_webhook_secret="")  # type: ignore[call-arg]

        no_secret_client = TestClient(no_secret_app)
        payload = _make_payload()
        body = json.dumps(payload).encode()

        response = no_secret_client.post(
            "/webhooks/clickup",
            content=body,
            headers={"X-Signature": "any", "Content-Type": "application/json"},
        )

        assert response.status_code == 500
