"""Celery tasks for sending Telegram notifications.

Handles two categories:
1. Scheduled report delivery — called after report generation tasks
2. Event-driven notifications — PVR bell, negative review alerts
"""

import asyncio
import uuid
from datetime import datetime, UTC

import structlog
from sqlalchemy import select, update

from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


# ------------------------------------------------------------------
# Scheduled report delivery tasks
# ------------------------------------------------------------------


async def _deliver_daily_reports() -> dict:
    """Deliver daily evening reports via Telegram.

    Finds undelivered reports (kombat_daily, daily_revenue) and sends
    them to the appropriate Telegram chats based on NotificationConfig.
    """
    from app.database import async_session
    from app.integrations.telegram.bot import TelegramBot
    from app.models.notification_config import NotificationConfig
    from app.models.report import Report

    bot = TelegramBot()
    sent = 0
    errors = 0

    async with async_session() as db:
        # Get undelivered daily reports
        result = await db.execute(
            select(Report).where(
                Report.delivered_telegram.is_(False),
                Report.type.in_(["kombat_daily", "daily_revenue"]),
            )
        )
        reports = list(result.scalars().all())

        for report in reports:
            try:
                if report.type == "kombat_daily":
                    sent += await _send_kombat_daily(
                        db, bot, report
                    )
                elif report.type == "daily_revenue":
                    sent += await _send_revenue(
                        db, bot, report
                    )

                # Mark as delivered
                await db.execute(
                    update(Report)
                    .where(Report.id == report.id)
                    .values(
                        delivered_telegram=True,
                        delivered_at=datetime.now(UTC),
                    )
                )
                await db.commit()
            except Exception:
                errors += 1
                await logger.aexception(
                    "Failed to deliver report",
                    report_id=str(report.id),
                    report_type=report.type,
                )

    summary = {"sent": sent, "errors": errors, "reports_processed": len(reports)}
    await logger.ainfo("Daily report delivery completed", **summary)
    return summary


async def _deliver_day_to_day_reports() -> dict:
    """Deliver day-to-day comparison reports via Telegram."""
    from app.database import async_session
    from app.integrations.telegram.bot import TelegramBot
    from app.models.notification_config import NotificationConfig
    from app.models.report import Report

    bot = TelegramBot()
    sent = 0
    errors = 0

    async with async_session() as db:
        result = await db.execute(
            select(Report).where(
                Report.delivered_telegram.is_(False),
                Report.type == "day_to_day",
            )
        )
        reports = list(result.scalars().all())

        for report in reports:
            try:
                sent += await _send_day_to_day(db, bot, report)

                await db.execute(
                    update(Report)
                    .where(Report.id == report.id)
                    .values(
                        delivered_telegram=True,
                        delivered_at=datetime.now(UTC),
                    )
                )
                await db.commit()
            except Exception:
                errors += 1
                await logger.aexception(
                    "Failed to deliver day-to-day report",
                    report_id=str(report.id),
                )

    summary = {"sent": sent, "errors": errors}
    await logger.ainfo("Day-to-day delivery completed", **summary)
    return summary


async def _deliver_monthly_reports() -> dict:
    """Deliver monthly Kombat summary reports via Telegram."""
    from app.database import async_session
    from app.integrations.telegram.bot import TelegramBot
    from app.models.report import Report

    bot = TelegramBot()
    sent = 0
    errors = 0

    async with async_session() as db:
        result = await db.execute(
            select(Report).where(
                Report.delivered_telegram.is_(False),
                Report.type == "kombat_monthly",
            )
        )
        reports = list(result.scalars().all())

        for report in reports:
            try:
                sent += await _send_kombat_monthly(db, bot, report)

                await db.execute(
                    update(Report)
                    .where(Report.id == report.id)
                    .values(
                        delivered_telegram=True,
                        delivered_at=datetime.now(UTC),
                    )
                )
                await db.commit()
            except Exception:
                errors += 1
                await logger.aexception(
                    "Failed to deliver monthly report",
                    report_id=str(report.id),
                )

    summary = {"sent": sent, "errors": errors}
    await logger.ainfo("Monthly delivery completed", **summary)
    return summary


# ------------------------------------------------------------------
# Event-driven notification tasks
# ------------------------------------------------------------------


async def _send_pvr_bell_notification(
    organization_id: str,
    branch_id: str,
    barber_name: str,
    threshold: int,
    bonus: int,
) -> dict:
    """Send PVR bell notification to the branch Telegram group."""
    from app.database import async_session
    from app.integrations.telegram.bot import TelegramBot
    from app.models.branch import Branch

    bot = TelegramBot()
    sent = 0

    async with async_session() as db:
        result = await db.execute(
            select(Branch).where(Branch.id == uuid.UUID(branch_id))
        )
        branch = result.scalar_one_or_none()

        if branch and branch.telegram_group_id:
            success = await bot.send_pvr_bell(
                chat_id=branch.telegram_group_id,
                barber_name=barber_name,
                threshold=threshold,
                bonus=bonus,
            )
            if success:
                sent += 1

        # Also send to configured notification targets
        sent += await _send_to_notif_targets(
            db, bot, uuid.UUID(organization_id),
            "pvr_threshold", branch_id=uuid.UUID(branch_id),
            send_fn=lambda chat_id: bot.send_pvr_bell(
                chat_id, barber_name, threshold, bonus
            ),
        )

    return {"sent": sent}


async def _send_negative_review_notification(
    organization_id: str,
    branch_name: str,
    barber_name: str,
    client_name: str | None,
    rating: int,
    comment: str | None,
    created_at: str,
    review_id: str,
    branch_id: str | None = None,
) -> dict:
    """Send negative review alert to manager/chef Telegram chats."""
    from app.database import async_session
    from app.integrations.telegram.bot import TelegramBot

    bot = TelegramBot()
    sent = 0

    async with async_session() as db:
        b_id = uuid.UUID(branch_id) if branch_id else None
        sent += await _send_to_notif_targets(
            db, bot, uuid.UUID(organization_id),
            "negative_review", branch_id=b_id,
            send_fn=lambda chat_id: bot.send_negative_review(
                chat_id=chat_id,
                branch_name=branch_name,
                barber_name=barber_name,
                client_name=client_name,
                rating=rating,
                comment=comment,
                created_at=created_at,
                review_id=review_id,
            ),
        )

    return {"sent": sent}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


async def _send_to_notif_targets(
    db,
    bot,
    organization_id: uuid.UUID,
    notification_type: str,
    branch_id: uuid.UUID | None,
    send_fn,
) -> int:
    """Look up NotificationConfig entries and call send_fn for each enabled target."""
    from app.models.notification_config import NotificationConfig

    stmt = select(NotificationConfig).where(
        NotificationConfig.organization_id == organization_id,
        NotificationConfig.notification_type == notification_type,
        NotificationConfig.is_enabled.is_(True),
    )
    if branch_id is not None:
        # Match configs for this specific branch OR org-wide (branch_id IS NULL)
        stmt = stmt.where(
            (NotificationConfig.branch_id == branch_id)
            | (NotificationConfig.branch_id.is_(None))
        )

    result = await db.execute(stmt)
    configs = list(result.scalars().all())

    sent = 0
    for config in configs:
        try:
            success = await send_fn(config.telegram_chat_id)
            if success:
                sent += 1
        except Exception:
            await logger.aexception(
                "Failed to send to notification target",
                config_id=str(config.id),
                chat_id=config.telegram_chat_id,
            )

    return sent


async def _send_kombat_daily(db, bot, report) -> int:
    """Send kombat_daily report to each branch's Telegram group."""
    from app.models.branch import Branch

    data = report.data or {}
    sent = 0

    for branch_entry in data.get("branches", []):
        branch_id_str = branch_entry.get("branch_id")
        if not branch_id_str:
            continue

        branch_id = uuid.UUID(branch_id_str)
        result = await db.execute(
            select(Branch).where(Branch.id == branch_id)
        )
        branch = result.scalar_one_or_none()

        if branch and branch.telegram_group_id:
            success = await bot.send_kombat_report(
                chat_id=branch.telegram_group_id,
                report_data=data,
                branch_data=branch_entry,
                branch_id=branch_id_str,
            )
            if success:
                sent += 1

        # Also send to notification targets configured for this type
        sent += await _send_to_notif_targets(
            db, bot, report.organization_id,
            "daily_rating", branch_id=branch_id,
            send_fn=lambda chat_id: bot.send_kombat_report(
                chat_id, data, branch_entry, branch_id_str
            ),
        )

    return sent


async def _send_revenue(db, bot, report) -> int:
    """Send daily_revenue report to owner notification targets."""
    data = report.data or {}
    sent = await _send_to_notif_targets(
        db, bot, report.organization_id,
        "daily_revenue", branch_id=None,
        send_fn=lambda chat_id: bot.send_revenue_report(chat_id, data),
    )
    return sent


async def _send_day_to_day(db, bot, report) -> int:
    """Send day-to-day report to owner notification targets."""
    data = report.data or {}
    sent = await _send_to_notif_targets(
        db, bot, report.organization_id,
        "day_to_day", branch_id=None,
        send_fn=lambda chat_id: bot.send_day_to_day(chat_id, data),
    )
    return sent


async def _send_kombat_monthly(db, bot, report) -> int:
    """Send monthly Kombat reports to each branch's Telegram group."""
    from app.models.branch import Branch

    data = report.data or {}
    sent = 0

    for branch_entry in data.get("branches", []):
        branch_id_str = branch_entry.get("branch_id")
        if not branch_id_str:
            continue

        branch_id = uuid.UUID(branch_id_str)
        result = await db.execute(
            select(Branch).where(Branch.id == branch_id)
        )
        branch = result.scalar_one_or_none()

        if branch and branch.telegram_group_id:
            success = await bot.send_kombat_monthly(
                chat_id=branch.telegram_group_id,
                report_data=data,
                branch_data=branch_entry,
                branch_id=branch_id_str,
            )
            if success:
                sent += 1

    return sent


# ------------------------------------------------------------------
# Celery task wrappers
# ------------------------------------------------------------------


@celery_app.task(
    name="deliver_daily_notifications",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def deliver_daily_notifications(self) -> dict:
    """Deliver daily reports (kombat, revenue) via Telegram.

    Scheduled to run shortly after daily report generation (22:35).
    """
    logger.info("Starting daily notification delivery", task_id=self.request.id)
    try:
        return asyncio.run(_deliver_daily_reports())
    except Exception as exc:
        logger.exception("Daily notification delivery failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="deliver_day_to_day_notifications",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def deliver_day_to_day_notifications(self) -> dict:
    """Deliver day-to-day reports via Telegram.

    Scheduled to run shortly after day-to-day report generation (11:05).
    """
    logger.info("Starting day-to-day notification delivery", task_id=self.request.id)
    try:
        return asyncio.run(_deliver_day_to_day_reports())
    except Exception as exc:
        logger.exception("Day-to-day notification delivery failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="deliver_monthly_notifications",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def deliver_monthly_notifications(self) -> dict:
    """Deliver monthly Kombat summary via Telegram.

    Scheduled to run shortly after monthly report generation (23:10).
    """
    logger.info("Starting monthly notification delivery", task_id=self.request.id)
    try:
        return asyncio.run(_deliver_monthly_reports())
    except Exception as exc:
        logger.exception("Monthly notification delivery failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="send_pvr_bell",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_pvr_bell(
    self,
    organization_id: str,
    branch_id: str,
    barber_name: str,
    threshold: int,
    bonus: int,
) -> dict:
    """Send PVR threshold bell notification (event-driven)."""
    logger.info(
        "Sending PVR bell",
        task_id=self.request.id,
        barber=barber_name,
        threshold=threshold,
    )
    try:
        return asyncio.run(
            _send_pvr_bell_notification(
                organization_id, branch_id, barber_name, threshold, bonus
            )
        )
    except Exception as exc:
        logger.exception("PVR bell notification failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="send_negative_review_alert",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_negative_review_alert(
    self,
    organization_id: str,
    branch_name: str,
    barber_name: str,
    client_name: str | None,
    rating: int,
    comment: str | None,
    created_at: str,
    review_id: str,
    branch_id: str | None = None,
) -> dict:
    """Send negative review alert notification (event-driven)."""
    logger.info(
        "Sending negative review alert",
        task_id=self.request.id,
        review_id=review_id,
        rating=rating,
    )
    try:
        return asyncio.run(
            _send_negative_review_notification(
                organization_id, branch_name, barber_name,
                client_name, rating, comment, created_at,
                review_id, branch_id,
            )
        )
    except Exception as exc:
        logger.exception("Negative review alert failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc
