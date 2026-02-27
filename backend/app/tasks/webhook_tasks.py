"""Celery tasks for processing YClients webhook events."""

import asyncio
from datetime import date

import structlog
from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


async def _process_record(company_id: int, record_id: int, event_status: str) -> None:
    """Async implementation of webhook record processing."""
    from app.database import async_session
    from app.integrations.yclients.client import YClientsClient
    from app.models.branch import Branch
    from app.models.visit import Visit
    from app.redis import redis_client
    from app.services.plans import PlanService
    from app.services.pvr import PVRService
    from app.services.sync import SyncService

    yclients = YClientsClient()
    try:
        async with async_session() as db:
            sync_service = SyncService(db=db, yclients=yclients)
            result = await sync_service.process_single_record(company_id, record_id)

            if result:
                # Resolve branch and barber for recalculation triggers
                branch_result = await db.execute(
                    select(Branch).where(Branch.yclients_company_id == company_id)
                )
                branch = branch_result.scalar_one_or_none()

                if branch:
                    # Find the visit we just upserted to get barber_id
                    visit_result = await db.execute(
                        select(Visit).where(
                            Visit.yclients_record_id == record_id,
                            Visit.organization_id == branch.organization_id,
                        )
                    )
                    visit = visit_result.scalar_one_or_none()

                    if visit:
                        # Trigger PVR recalculation for this barber
                        pvr_service = PVRService(db=db, redis=redis_client)
                        await pvr_service.recalculate_barber(
                            barber_id=visit.barber_id,
                            organization_id=branch.organization_id,
                            target_month=date.today(),
                        )
                        await logger.ainfo(
                            "PVR recalculated after webhook",
                            company_id=company_id,
                            record_id=record_id,
                            barber_id=str(visit.barber_id),
                        )

                    # Update plan progress for this branch
                    plan_service = PlanService(db=db, redis=redis_client)
                    await plan_service.update_progress(branch.id)
                    await logger.ainfo(
                        "Plan progress updated after webhook",
                        company_id=company_id,
                        record_id=record_id,
                        branch_id=str(branch.id),
                    )

                    # Placeholder: trigger Rating Engine recalculation
                    logger.info(
                        "Rating recalculation trigger [PLACEHOLDER]",
                        company_id=company_id,
                        record_id=record_id,
                    )

                    # Placeholder: push WebSocket update
                    logger.info(
                        "WebSocket push [PLACEHOLDER]",
                        company_id=company_id,
                        record_id=record_id,
                    )
    finally:
        await yclients.close()


@celery_app.task(
    name="process_yclients_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_yclients_webhook(
    self,
    company_id: int,
    record_id: int,
    event_status: str,
) -> dict:
    """Process a single YClients webhook event.

    Bridges synchronous Celery with async SyncService via asyncio.run().
    """
    logger.info(
        "Processing webhook task",
        task_id=self.request.id,
        company_id=company_id,
        record_id=record_id,
        event_status=event_status,
    )

    try:
        asyncio.run(_process_record(company_id, record_id, event_status))
        return {
            "status": "ok",
            "company_id": company_id,
            "record_id": record_id,
        }
    except Exception as exc:
        logger.exception(
            "Webhook task failed",
            task_id=self.request.id,
            company_id=company_id,
            record_id=record_id,
            error=str(exc),
        )
        raise self.retry(exc=exc) from exc
