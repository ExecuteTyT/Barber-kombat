"""Webhook endpoints for external service integrations."""

import structlog
from fastapi import APIRouter, Request, status

from app.auth.webhook import validate_webhook_signature
from app.config import settings
from app.schemas.webhook import WebhookResponse
from app.tasks.webhook_tasks import process_yclients_webhook

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/yclients",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def receive_yclients_webhook(request: Request) -> WebhookResponse:
    """Receive and queue a YClients webhook event for async processing.

    Always returns 200 OK to prevent retry storms from YClients.
    Invalid signatures are logged but not retried.
    """
    raw_body = await request.body()

    # Validate HMAC signature
    signature = request.headers.get("X-Signature", "")
    if not signature:
        signature = request.headers.get("Content-Signature", "")

    if not validate_webhook_signature(
        raw_body, signature, settings.yclients_webhook_secret
    ):
        await logger.awarning(
            "Webhook signature validation failed",
            remote_addr=request.client.host if request.client else "unknown",
        )
        return WebhookResponse(ok=False)

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        await logger.awarning("Webhook payload is not valid JSON")
        return WebhookResponse(ok=False)

    company_id = payload.get("company_id", 0)
    resource = payload.get("resource", "unknown")
    event_status = payload.get("status", "unknown")

    # Extract record_id from data
    data = payload.get("data", {})
    record_id = data.get("id") if isinstance(data, dict) else None

    await logger.ainfo(
        "YClients webhook received",
        company_id=company_id,
        resource=resource,
        event_status=event_status,
        record_id=record_id,
    )

    # Only process record events with valid identifiers
    if resource != "record" or not company_id or not record_id:
        return WebhookResponse(ok=True)

    # Enqueue Celery task
    task = process_yclients_webhook.delay(
        company_id=company_id,
        record_id=record_id,
        event_status=event_status,
    )

    await logger.ainfo(
        "Webhook task enqueued",
        task_id=task.id,
        company_id=company_id,
        record_id=record_id,
        event_status=event_status,
    )

    return WebhookResponse(ok=True)
