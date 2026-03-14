"""Celery tasks for review processing.

- check_unprocessed_reviews: every 30 min, sends reminders for overdue unprocessed reviews.
- send_review_request: delayed task, sends review form link to client after visit via WhatsApp/Telegram.
"""

import asyncio
import uuid

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


async def _check_unprocessed() -> dict:
    """Find and send reminders for all overdue unprocessed reviews."""
    from app.database import async_session
    from app.redis import redis_client
    from app.services.reviews import ReviewService

    async with async_session() as db:
        service = ReviewService(db=db, redis=redis_client)
        sent = await service.send_overdue_reminders()

    return {"reminders_sent": sent}


async def _send_review_request(visit_id: str) -> dict:
    """Send review form link to client for a given visit.

    Tries WhatsApp first (if client has phone and WhatsApp is configured),
    falls back to Telegram bot (if client has telegram_id — not currently supported),
    otherwise logs the URL for dev/debugging.
    """
    from sqlalchemy import select

    from app.config import settings
    from app.database import async_session
    from app.integrations.telegram.bot import format_review_request
    from app.integrations.whatsapp.client import WhatsAppClient
    from app.models.client import Client
    from app.models.user import User
    from app.models.visit import Visit

    vid = uuid.UUID(visit_id)

    async with async_session() as db:
        # Load visit with related data
        visit_result = await db.execute(select(Visit).where(Visit.id == vid))
        visit = visit_result.scalar_one_or_none()

        if not visit:
            logger.warning("Visit not found for review request", visit_id=visit_id)
            return {"status": "skip", "reason": "visit_not_found"}

        if visit.review_request_sent:
            logger.info("Review request already sent", visit_id=visit_id)
            return {"status": "skip", "reason": "already_sent"}

        if visit.status != "completed":
            logger.info("Visit not completed, skipping review request", visit_id=visit_id)
            return {"status": "skip", "reason": "not_completed"}

        # Check if review already exists for this visit
        if visit.review is not None:
            logger.info("Review already exists, skipping request", visit_id=visit_id)
            return {"status": "skip", "reason": "review_exists"}

        # Load client
        client = None
        if visit.client_id:
            client_result = await db.execute(select(Client).where(Client.id == visit.client_id))
            client = client_result.scalar_one_or_none()

        if not client:
            logger.warning("No client linked to visit", visit_id=visit_id)
            visit.review_request_sent = True
            await db.commit()
            return {"status": "skip", "reason": "no_client"}

        # Load barber name
        barber_result = await db.execute(select(User).where(User.id == visit.barber_id))
        barber = barber_result.scalar_one_or_none()
        barber_name = barber.name if barber else "мастер"

        # Build review URL
        base_url = settings.review_form_url.rstrip("/")
        if not base_url:
            # Dev fallback: use localhost
            base_url = "http://localhost:3000/review"

        review_url = (
            f"{base_url}?branch={visit.branch_id}"
            f"&barber={visit.barber_id}"
            f"&visit={visit.id}"
        )

        message_text = format_review_request(barber_name, review_url)
        sent = False

        # Try WhatsApp first
        if client.phone:
            wa = WhatsAppClient()
            try:
                sent = await wa.send_message(client.phone, message_text)
            finally:
                await wa.close()

            if sent:
                logger.info(
                    "Review request sent via WhatsApp",
                    visit_id=visit_id,
                    phone=client.phone,
                )

        # Log for dev/debugging if not sent
        if not sent:
            logger.info(
                "Review request not sent (no WhatsApp or not configured), logging URL",
                visit_id=visit_id,
                client_name=client.name,
                review_url=review_url,
            )

        # Mark as sent regardless (to avoid retrying endlessly)
        visit.review_request_sent = True
        await db.commit()

        return {
            "status": "sent" if sent else "logged",
            "visit_id": visit_id,
            "channel": "whatsapp" if sent else "none",
            "review_url": review_url,
        }


@celery_app.task(
    name="check_unprocessed_reviews",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def check_unprocessed_reviews(self) -> dict:
    """Scheduled every 30 min — sends reminders for overdue unprocessed reviews."""
    logger.info("Starting unprocessed reviews check", task_id=self.request.id)
    try:
        return asyncio.run(_check_unprocessed())
    except Exception as exc:
        logger.exception("Unprocessed reviews check failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="send_review_request",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def send_review_request(self, visit_id: str) -> dict:
    """Send review form link to client after visit completion.

    Called with a delay (default 30 min) after visit is marked completed.
    """
    logger.info("Sending review request", task_id=self.request.id, visit_id=visit_id)
    try:
        return asyncio.run(_send_review_request(visit_id))
    except Exception as exc:
        logger.exception("Review request task failed", task_id=self.request.id, visit_id=visit_id)
        raise self.retry(exc=exc) from exc
