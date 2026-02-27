"""Celery task for monthly reset.

Schedule: 1st of each month at 00:05 (Moscow time).

Finalizes the previous month:
- Determines champions per branch
- Freezes prize funds into reports
- Creates new PVR records with zeroes
- Copies plans to the new month
"""

import asyncio
from datetime import date

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


async def _run_monthly_reset(target_month: date | None = None) -> dict:
    """Run monthly reset for all active organizations.

    Args:
        target_month: Month to finalize (1st day). Defaults to the
            previous month relative to today.
    """
    from app.database import async_session
    from app.services.monthly_reset import MonthlyResetService

    if target_month is None:
        today = date.today()
        # We run on the 1st of the new month, so finalize previous month
        if today.month == 1:
            target_month = date(today.year - 1, 12, 1)
        else:
            target_month = date(today.year, today.month - 1, 1)

    target_month = target_month.replace(day=1)

    async with async_session() as db:
        service = MonthlyResetService(db=db)
        result = await service.reset_all_organizations(target_month)

    await logger.ainfo("Monthly reset task completed", **result)
    return result


@celery_app.task(
    name="monthly_reset",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def monthly_reset(self) -> dict:
    """Scheduled at 1st of month, 00:05 — finalizes the previous month."""
    logger.info("Starting monthly reset task", task_id=self.request.id)
    try:
        return asyncio.run(_run_monthly_reset())
    except Exception as exc:
        logger.exception("Monthly reset task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc
