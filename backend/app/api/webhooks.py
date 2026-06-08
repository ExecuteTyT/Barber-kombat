"""Webhook endpoints for external service integrations."""

import hmac
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.webhook import validate_webhook_signature
from app.config import settings
from app.database import get_db
from app.schemas.webhook import WebhookResponse
from app.services.surveys import SurveyService
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

    if not validate_webhook_signature(raw_body, signature, settings.yclients_webhook_secret):
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


@router.post(
    "/yandex-forms",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def receive_yandex_forms_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    """Receive a guest-survey submission from Yandex Forms.

    Auth: a shared secret (``settings.yandex_forms_secret``) sent either as the
    ``X-Survey-Secret`` header or a ``secret`` field in the body. Always returns
    200 to avoid Yandex Forms retry storms; bad secret/payload are logged.
    """
    try:
        payload = await request.json()
    except Exception:
        # Yandex Forms can also send form-urlencoded — fall back to form fields.
        try:
            form = await request.form()
            payload = {k: v for k, v in form.items()}
        except Exception:
            await logger.awarning("Yandex Forms webhook: unparseable payload")
            return WebhookResponse(ok=False)

    if not isinstance(payload, dict):
        return WebhookResponse(ok=False)

    # Yandex Forms' "JSON-RPC" integration mode wraps the answers in a "params"
    # object; flatten it so either integration mode ("заданным методом" or
    # JSON-RPC) produces the same flat payload.
    if isinstance(payload.get("params"), dict):
        payload = {**payload, **payload["params"]}

    secret = request.headers.get("X-Survey-Secret") or str(payload.get("secret", ""))
    expected = settings.yandex_forms_secret
    if not expected or not hmac.compare_digest(secret, expected):
        await logger.awarning(
            "Yandex Forms webhook: bad secret",
            remote_addr=request.client.host if request.client else "unknown",
        )
        return WebhookResponse(ok=False)

    try:
        await SurveyService(db=db).parse_and_store(payload)
    except Exception:
        await logger.aexception("Yandex Forms webhook: processing failed")
        return WebhookResponse(ok=False)

    return WebhookResponse(ok=True)
