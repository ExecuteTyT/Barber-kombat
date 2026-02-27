"""Celery tasks for scheduled report generation.

Schedule (Moscow time):
- 22:30 — daily reports: revenue, clients, kombat daily
- 11:00 — day-to-day comparison
- Last day of month, 23:00 — monthly reports: kombat monthly
"""

import asyncio
import calendar
from datetime import date

import structlog
from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


async def _generate_daily(target_date: date | None = None) -> dict:
    """Generate all daily evening reports for every organization.

    Reports generated: daily_revenue, clients, kombat_daily.
    """
    from app.database import async_session
    from app.models.organization import Organization
    from app.services.reports import ReportService

    report_date = target_date or date.today()
    orgs_processed = 0
    errors = 0

    async with async_session() as db:
        result = await db.execute(select(Organization).where(Organization.is_active.is_(True)))
        orgs = result.scalars().all()

        for org in orgs:
            try:
                service = ReportService(db=db)
                await service.generate_daily_revenue(org.id, report_date)
                await service.generate_clients_report(org.id, report_date)
                await service.generate_kombat_daily(org.id, report_date)
                orgs_processed += 1
            except Exception:
                errors += 1
                await logger.aexception(
                    "Daily report generation failed",
                    org_id=str(org.id),
                    date=str(report_date),
                )

    summary = {
        "date": str(report_date),
        "orgs_processed": orgs_processed,
        "errors": errors,
    }
    await logger.ainfo("Daily reports generated", **summary)
    return summary


async def _generate_day_to_day(target_date: date | None = None) -> dict:
    """Generate day-to-day comparison reports for every organization."""
    from app.database import async_session
    from app.models.organization import Organization
    from app.services.reports import ReportService

    report_date = target_date or date.today()
    orgs_processed = 0
    errors = 0

    async with async_session() as db:
        result = await db.execute(select(Organization).where(Organization.is_active.is_(True)))
        orgs = result.scalars().all()

        for org in orgs:
            try:
                service = ReportService(db=db)
                # Network-wide report (no branch_id)
                await service.generate_day_to_day(org.id, report_date, branch_id=None)
                orgs_processed += 1
            except Exception:
                errors += 1
                await logger.aexception(
                    "Day-to-day report generation failed",
                    org_id=str(org.id),
                    date=str(report_date),
                )

    summary = {
        "date": str(report_date),
        "orgs_processed": orgs_processed,
        "errors": errors,
    }
    await logger.ainfo("Day-to-day reports generated", **summary)
    return summary


async def _generate_monthly(target_month: date | None = None) -> dict:
    """Generate monthly summary reports for every organization.

    Reports generated: kombat_monthly.
    Runs on the last day of the month at 23:00.
    """
    from app.database import async_session
    from app.models.organization import Organization
    from app.services.reports import ReportService

    month = (target_month or date.today()).replace(day=1)
    orgs_processed = 0
    errors = 0

    async with async_session() as db:
        result = await db.execute(select(Organization).where(Organization.is_active.is_(True)))
        orgs = result.scalars().all()

        for org in orgs:
            try:
                service = ReportService(db=db)
                await service.generate_kombat_monthly(org.id, month)
                orgs_processed += 1
            except Exception:
                errors += 1
                await logger.aexception(
                    "Monthly report generation failed",
                    org_id=str(org.id),
                    month=str(month),
                )

    summary = {
        "month": str(month),
        "orgs_processed": orgs_processed,
        "errors": errors,
    }
    await logger.ainfo("Monthly reports generated", **summary)
    return summary


# ------------------------------------------------------------------
# Celery task wrappers
# ------------------------------------------------------------------


@celery_app.task(
    name="generate_daily_reports",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def generate_daily_reports(self) -> dict:
    """Scheduled at 22:30 — generates daily revenue, clients, and kombat reports."""
    logger.info("Starting daily reports task", task_id=self.request.id)
    try:
        return asyncio.run(_generate_daily())
    except Exception as exc:
        logger.exception("Daily reports task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="generate_day_to_day",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def generate_day_to_day(self) -> dict:
    """Scheduled at 11:00 — generates day-to-day comparison reports."""
    logger.info("Starting day-to-day reports task", task_id=self.request.id)
    try:
        return asyncio.run(_generate_day_to_day())
    except Exception as exc:
        logger.exception("Day-to-day reports task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="generate_monthly_reports",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def generate_monthly_reports(self) -> dict:
    """Scheduled at last day of month, 23:00 — generates monthly summaries.

    The task checks if today is actually the last day of the month
    before running, so it can safely be scheduled for day 28.
    """
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]

    if today.day != last_day:
        logger.info(
            "Monthly reports skipped — not last day of month",
            task_id=self.request.id,
            today=str(today),
            last_day=last_day,
        )
        return {"status": "skipped", "reason": "not_last_day"}

    logger.info("Starting monthly reports task", task_id=self.request.id)
    try:
        return asyncio.run(_generate_monthly())
    except Exception as exc:
        logger.exception("Monthly reports task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc
