"""Tests for webhook endpoint, signature validation, and task dispatch."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.webhook import validate_webhook_signature
from app.main import app

WEBHOOK_SECRET = "test-webhook-secret"


# --- Helpers ---


def build_signed_webhook(
    payload: dict,
    secret: str = WEBHOOK_SECRET,
) -> tuple[bytes, str]:
    """Build a webhook body and its HMAC-SHA256 signature."""
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, sig


def sample_webhook_payload(
    company_id: int = 555,
    record_id: int = 1001,
    resource: str = "record",
    status: str = "completed",
) -> dict:
    """Build a sample YClients webhook payload."""
    return {
        "company_id": company_id,
        "resource": resource,
        "status": status,
        "data": {"id": record_id, "staff_id": 10, "cost": 1500.0},
    }


# --- Tests: Signature Validation ---


class TestWebhookSignatureValidation:
    def test_valid_signature(self):
        body = b'{"company_id": 555}'
        sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert validate_webhook_signature(body, sig, WEBHOOK_SECRET) is True

    def test_invalid_signature(self):
        body = b'{"company_id": 555}'
        assert validate_webhook_signature(body, "invalid-sig", WEBHOOK_SECRET) is False

    def test_tampered_body(self):
        body = b'{"company_id": 555}'
        sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        tampered = b'{"company_id": 999}'
        assert validate_webhook_signature(tampered, sig, WEBHOOK_SECRET) is False

    def test_empty_secret_skips_validation(self):
        body = b'{"company_id": 555}'
        assert validate_webhook_signature(body, "", "") is True

    def test_empty_signature_fails(self):
        body = b'{"company_id": 555}'
        assert validate_webhook_signature(body, "", WEBHOOK_SECRET) is False

    def test_wrong_secret_fails(self):
        body = b'{"company_id": 555}'
        sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert validate_webhook_signature(body, sig, "wrong-secret") is False


# --- Tests: Webhook Endpoint ---


class TestWebhookEndpoint:
    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_valid_webhook_dispatches_task(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = WEBHOOK_SECRET
        mock_task.delay.return_value = MagicMock(id="test-task-id")

        payload = sample_webhook_payload()
        body, sig = build_signed_webhook(payload)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": sig,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

        mock_task.delay.assert_called_once_with(
            company_id=555,
            record_id=1001,
            event_status="completed",
        )

    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_invalid_signature_returns_ok_false(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = WEBHOOK_SECRET

        payload = sample_webhook_payload()
        body = json.dumps(payload).encode("utf-8")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": "bad-signature",
                },
            )

        assert response.status_code == 200
        assert response.json()["ok"] is False
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_non_record_resource_ignored(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = WEBHOOK_SECRET

        payload = sample_webhook_payload(resource="client")
        body, sig = build_signed_webhook(payload)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": sig,
                },
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_missing_record_id_ignored(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = WEBHOOK_SECRET

        payload = {
            "company_id": 555,
            "resource": "record",
            "status": "completed",
            "data": {},  # no id
        }
        body, sig = build_signed_webhook(payload)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": sig,
                },
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_content_signature_header_fallback(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = WEBHOOK_SECRET
        mock_task.delay.return_value = MagicMock(id="test-task-id")

        payload = sample_webhook_payload()
        body, sig = build_signed_webhook(payload)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Signature": sig,  # fallback header
                },
            )

        assert response.status_code == 200
        assert response.json()["ok"] is True
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_invalid_json_returns_ok_false(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = ""  # skip sig validation

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=b"not-json{{{",
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        assert response.json()["ok"] is False
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.api.webhooks.process_yclients_webhook")
    @patch("app.api.webhooks.settings")
    async def test_task_receives_correct_event_status(self, mock_settings, mock_task):
        mock_settings.yclients_webhook_secret = WEBHOOK_SECRET
        mock_task.delay.return_value = MagicMock(id="test-task-id")

        payload = sample_webhook_payload(status="cancelled")
        body, sig = build_signed_webhook(payload)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/webhooks/yclients",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Signature": sig,
                },
            )

        assert response.status_code == 200
        mock_task.delay.assert_called_once_with(
            company_id=555,
            record_id=1001,
            event_status="cancelled",
        )
