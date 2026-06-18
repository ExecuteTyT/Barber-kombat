"""Celery task: sync quality-control call tasks from DataHeroes.

Pulls "Нужно связаться" tasks for every branch that has a
``datahero_project_id`` and upserts them into ``dh_call_tasks`` so admins see
them on the Calls screen. Also retries pushing any locally-marked-contacted
rows that haven't reached DataHeroes yet. Gated by ``dataheroes_enabled``.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.tasks.celery_app import celery_app

logger = structlog.stdlib.get_logger()


async def _sync_all_branches() -> dict:
    from app.database import task_sessionmaker
    from app.integrations.dataheroes.client import DataHeroesClient
    from app.models.branch import Branch
    from app.models.dh_call_task import DHCallTask

    if not settings.dataheroes_enabled:
        return {"skipped": "dataheroes_disabled"}

    today = date.today()
    branches_processed = 0
    total_synced = 0
    total_pushed = 0
    errors = 0

    dh = DataHeroesClient()
    try:
        async with task_sessionmaker() as Session:
            async with Session() as db:
                result = await db.execute(
                    select(Branch).where(
                        Branch.is_active.is_(True),
                        Branch.datahero_project_id.isnot(None),
                        Branch.datahero_activations.isnot(None),
                    )
                )
                branches = result.scalars().all()

            for branch in branches:
                # Fresh session per branch so one failure doesn't poison the rest.
                async with Session() as db:
                    try:
                        tasks = await dh.get_qc_tasks(
                            branch.datahero_project_id,
                            activations=branch.datahero_activations,
                        )
                        fetched_ids = [t.communication_id for t in tasks]

                        for t in tasks:
                            stmt = pg_insert(DHCallTask).values(
                                id=uuid.uuid4(),
                                organization_id=branch.organization_id,
                                branch_id=branch.id,
                                dataheroes_task_id=t.communication_id,
                                dh_project_id=t.project_id or branch.datahero_project_id,
                                dh_client_id=t.client_id,
                                client_name=t.client_name_with_num or "",
                                phone=t.client_phone,
                                reason=t.activation_name,
                                visit_count=t.client_visit_cnt,
                                task_date=today,
                                synced_at=datetime.now(UTC),
                            )
                            # Update only descriptive fields on conflict — never
                            # reset a locally-set "contacted" status.
                            stmt = stmt.on_conflict_do_update(
                                constraint="uq_dh_call_branch_task",
                                set_={
                                    "dh_project_id": stmt.excluded.dh_project_id,
                                    "dh_client_id": stmt.excluded.dh_client_id,
                                    "client_name": stmt.excluded.client_name,
                                    "phone": stmt.excluded.phone,
                                    "reason": stmt.excluded.reason,
                                    "visit_count": stmt.excluded.visit_count,
                                    "synced_at": stmt.excluded.synced_at,
                                },
                            )
                            await db.execute(stmt)

                        # Prune pending rows no longer in DataHeroes' list
                        # (handled directly in DataHeroes). Keep contacted rows.
                        prune = await db.execute(
                            select(DHCallTask).where(
                                DHCallTask.branch_id == branch.id,
                                DHCallTask.status == "pending",
                                DHCallTask.dataheroes_task_id.notin_(fetched_ids)
                                if fetched_ids
                                else DHCallTask.dataheroes_task_id.isnot(None),
                            )
                        )
                        for stale in prune.scalars().all():
                            await db.delete(stale)

                        await db.commit()
                        total_synced += len(tasks)
                        branches_processed += 1
                    except Exception:
                        errors += 1
                        await db.rollback()
                        await logger.aexception(
                            "DataHeroes sync failed for branch",
                            branch_id=str(branch.id),
                        )

                # Retry unpushed contacted marks for this branch.
                async with Session() as db:
                    try:
                        unpushed = await db.execute(
                            select(DHCallTask).where(
                                DHCallTask.branch_id == branch.id,
                                DHCallTask.status == "contacted",
                                DHCallTask.pushed.is_(False),
                            )
                        )
                        for row in unpushed.scalars().all():
                            if not row.dh_project_id:
                                continue
                            await dh.mark_contacted(
                                communication_id=row.dataheroes_task_id,
                                project_id=row.dh_project_id,
                                client_id=row.dh_client_id,
                            )
                            row.pushed = True
                            total_pushed += 1
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        await logger.aexception(
                            "DataHeroes retry-push failed for branch",
                            branch_id=str(branch.id),
                        )
    finally:
        await dh.close()

    summary = {
        "branches_processed": branches_processed,
        "total_synced": total_synced,
        "total_pushed": total_pushed,
        "errors": errors,
    }
    await logger.ainfo("DataHeroes sync completed", **summary)
    return summary


@celery_app.task(
    name="sync_dataheroes_tasks",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def sync_dataheroes_tasks(self) -> dict:
    """Periodic task: pull DataHeroes QC call tasks for all branches."""
    logger.info("Starting DataHeroes sync task", task_id=self.request.id)
    try:
        return asyncio.run(_sync_all_branches())
    except Exception as exc:
        logger.exception("DataHeroes sync task failed", task_id=self.request.id)
        raise self.retry(exc=exc) from exc
