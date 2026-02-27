"""Celery task for checking unprocessed reviews.

Schedule: every 30 minutes.
Finds negative reviews that have been unprocessed for over 2 hours
and sends reminder notifications via WebSocket.
"""

import asyncio

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
