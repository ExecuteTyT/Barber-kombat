"""Celery tasks for periodic polling and full sync of YClients data."""

import asyncio
from datetime import date, timedelta

import structlog
from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


async def _poll_all_branches() -> dict:
    """Poll YClients for recent records across all active branches.

    Fetches records from the last 20 minutes for every active branch
    that has a yclients_company_id configured.

    Returns a summary dict with total synced count.
    """
    from app.database import async_session
    from app.integrations.yclients.client import YClientsClient
    from app.models.branch import Branch
    from app.redis import redis_client
    from app.services.plans import PlanService
    from app.services.pvr import PVRService
    from app.services.sync import SyncService

    today = date.today()
    total_synced = 0
    branches_processed = 0
    errors = 0

    yclients = YClientsClient()
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Branch).where(
                    Branch.is_active.is_(True),
                    Branch.yclients_company_id.isnot(None),
                )
            )
            branches = result.scalars().all()

            sync_service = SyncService(db=db, yclients=yclients)

            for branch in branches:
                try:
                    synced = await sync_service.sync_records(
                        branch.id, today, today
                    )
                    total_synced += synced
                    branches_processed += 1

                    if synced > 0:
                        logger.info(
                            "Polling: records synced for branch",
                            branch_id=str(branch.id),
                            branch_name=branch.name,
                            synced=synced,
                        )

                        # Recalculate PVR for all barbers in this branch
                        pvr_service = PVRService(db=db, redis=redis_client)
                        await pvr_service.recalculate_branch(branch.id, today)
                        await logger.ainfo(
                            "PVR recalculated for branch after polling",
                            branch_id=str(branch.id),
                        )

                        # Update plan progress for this branch
                        plan_service = PlanService(db=db, redis=redis_client)
                        await plan_service.update_progress(branch.id)
                        await logger.ainfo(
                            "Plan progress updated for branch after polling",
                            branch_id=str(branch.id),
                        )

                        # Recalculate daily rating for this branch
                        from app.services.rating import RatingEngine

                        rating_engine = RatingEngine(db=db, redis=redis_client)
                        await rating_engine.recalculate(branch.id, today)
                        await logger.ainfo(
                            "Rating recalculated for branch after polling",
                            branch_id=str(branch.id),
                        )

                except Exception:
                    errors += 1
                    logger.exception(
                        "Polling: error syncing branch",
                        branch_id=str(branch.id),
                    )
    finally:
        await yclients.close()

    summary = {
        "branches_processed": branches_processed,
        "total_synced": total_synced,
        "errors": errors,
    }
    logger.info("Polling completed", **summary)
    return summary


async def _full_sync_all_branches() -> dict:
    """Full daily sync — reconcile all of yesterday's data.

    For every active branch:
    1. Sync staff (catch new hires)
    2. Sync all records from yesterday

    Returns a summary dict.
    """
    from app.database import async_session
    from app.integrations.yclients.client import YClientsClient
    from app.models.branch import Branch
    from app.redis import redis_client
    from app.services.plans import PlanService
    from app.services.pvr import PVRService
    from app.services.sync import SyncService

    yesterday = date.today() - timedelta(days=1)
    total_synced = 0
    staff_synced = 0
    branches_processed = 0
    errors = 0

    yclients = YClientsClient()
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Branch).where(
                    Branch.is_active.is_(True),
                    Branch.yclients_company_id.isnot(None),
                )
            )
            branches = result.scalars().all()

            sync_service = SyncService(db=db, yclients=yclients)
            pvr_service = PVRService(db=db, redis=redis_client)

            for branch in branches:
                try:
                    # Sync staff first (catch new hires / fired)
                    s_count = await sync_service.sync_staff(branch.id)
                    staff_synced += s_count

                    # Sync all records from yesterday
                    r_count = await sync_service.sync_records(
                        branch.id, yesterday, yesterday
                    )
                    total_synced += r_count
                    branches_processed += 1

                    logger.info(
                        "Full sync: branch completed",
                        branch_id=str(branch.id),
                        branch_name=branch.name,
                        staff_synced=s_count,
                        records_synced=r_count,
                    )

                except Exception:
                    errors += 1
                    logger.exception(
                        "Full sync: error syncing branch",
                        branch_id=str(branch.id),
                    )

            # Recalculate PVR for all branches (current month)
            for branch in branches:
                try:
                    await pvr_service.recalculate_branch(branch.id, date.today())
                except Exception:
                    await logger.aexception(
                        "Full sync: PVR recalculation failed",
                        branch_id=str(branch.id),
                    )
            await logger.ainfo(
                "PVR recalculated for all branches after full sync",
                branches=len(branches),
            )

            # Update plan progress for all branches
            plan_service = PlanService(db=db, redis=redis_client)
            for branch in branches:
                try:
                    await plan_service.update_progress(branch.id)
                except Exception:
                    await logger.aexception(
                        "Full sync: plan progress update failed",
                        branch_id=str(branch.id),
                    )
            await logger.ainfo(
                "Plan progress updated for all branches after full sync",
                branches=len(branches),
            )

            # Recalculate ratings for yesterday for all branches
            from app.services.rating import RatingEngine

            rating_engine = RatingEngine(db=db, redis=redis_client)
            for branch in branches:
                try:
                    await rating_engine.recalculate(branch.id, yesterday)
                except Exception:
                    await logger.aexception(
                        "Full sync: rating recalculation failed",
                        branch_id=str(branch.id),
                    )
            await logger.ainfo(
                "Ratings recalculated for all branches after full sync",
                date=str(yesterday),
            )

            # Generate daily reports for yesterday's data
            from app.models.organization import Organization
            from app.services.reports import ReportService

            org_result = await db.execute(
                select(Organization.id).where(Organization.is_active.is_(True))
            )
            org_ids = org_result.scalars().all()
            for org_id in org_ids:
                try:
                    report_svc = ReportService(db=db)
                    await report_svc.generate_daily_revenue(org_id, yesterday)
                    await report_svc.generate_clients_report(org_id, yesterday)
                    await report_svc.generate_kombat_daily(org_id, yesterday)
                except Exception:
                    await logger.aexception(
                        "Full sync: report generation failed",
                        org_id=str(org_id),
                    )
            await logger.ainfo(
                "Reports generated after full sync",
                date=str(yesterday),
            )
    finally:
        await yclients.close()

    summary = {
        "date": str(yesterday),
        "branches_processed": branches_processed,
        "total_synced": total_synced,
        "staff_synced": staff_synced,
        "errors": errors,
    }
    logger.info("Full sync completed", **summary)
    return summary


@celery_app.task(
    name="poll_yclients",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def poll_yclients(self) -> dict:
    """Periodic task: poll YClients every 10 minutes."""
    logger.info("Starting polling task", task_id=self.request.id)
    try:
        return asyncio.run(_poll_all_branches())
    except Exception as exc:
        logger.exception("Polling task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="full_sync_yclients",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def full_sync_yclients(self) -> dict:
    """Daily task: full sync at 04:00 Moscow time."""
    logger.info("Starting full sync task", task_id=self.request.id)
    try:
        return asyncio.run(_full_sync_all_branches())
    except Exception as exc:
        logger.exception("Full sync task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc
