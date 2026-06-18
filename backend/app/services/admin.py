"""Admin service — metrics, tasks, and history for branch admins."""

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admin_call_log import AdminCallLog
from app.models.branch import Branch
from app.models.client import Client
from app.models.dh_call_task import DHCallTask
from app.models.user import User
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()


class AdminService:
    """Queries for admin dashboard screens."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metrics(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Return daily metrics for a branch."""
        branch = await self._get_branch(branch_id)
        branch_name = branch.name if branch else "Unknown"
        org_id = branch.organization_id if branch else None

        # Records today (completed visits)
        records_today = await self._count_visits(branch_id, target_date)

        # Products sold today
        products_sold = await self._sum_products(branch_id, target_date)

        # Tomorrow's bookings (confirmed = the YClients confirmation flag)
        tomorrow = target_date + timedelta(days=1)
        total_tomorrow = await self._count_visits(branch_id, tomorrow, include_pending=True)
        confirmed_tomorrow = await self._count_visits(branch_id, tomorrow, confirmed=True)

        # Birthday fill rate
        filled_birthdays = 0
        total_clients = 0
        if org_id:
            filled_birthdays, total_clients = await self._birthday_stats(org_id, branch_id)

        return {
            "branch_id": str(branch_id),
            "branch_name": branch_name,
            "date": str(target_date),
            "records_today": records_today,
            "products_sold": products_sold,
            "confirmed_tomorrow": confirmed_tomorrow,
            "total_tomorrow": total_tomorrow,
            "filled_birthdays": filled_birthdays,
            "total_clients": total_clients,
        }

    async def get_tasks(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Return actionable tasks for branch admin."""
        tomorrow = target_date + timedelta(days=1)

        # Unconfirmed records for tomorrow (pending visits)
        unconfirmed = await self._unconfirmed_records(branch_id, tomorrow)

        # Clients without birthday
        unfilled = await self._unfilled_birthdays(branch_id)

        # Unprocessed checks (visits without proper status today)
        unprocessed = await self._unprocessed_checks(branch_id, target_date)

        return {
            "branch_id": str(branch_id),
            "date": str(target_date),
            "unconfirmed_records": unconfirmed,
            "unfilled_birthdays": unfilled,
            "unprocessed_checks": unprocessed,
        }

    async def confirm_records(
        self,
        branch_id: uuid.UUID,
        record_ids: list[str],
    ) -> int:
        """Mark visit records as confirmed. Returns count of updated records."""
        if not record_ids:
            return 0

        uuids = [uuid.UUID(rid) for rid in record_ids]
        result = await self.db.execute(
            select(Visit).where(
                Visit.branch_id == branch_id,
                Visit.id.in_(uuids),
                Visit.status == "pending",
            )
        )
        visits = list(result.scalars().all())
        for visit in visits:
            visit.status = "confirmed"
        await self.db.commit()
        return len(visits)

    async def get_call_list(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Upcoming appointments to confirm + confirmation/call-progress stats.

        ``to_call`` = upcoming scheduled visits that YClients hasn't marked
        confirmed; each is annotated with whether an admin already logged a call
        today. Also returns the objective confirmation rate of upcoming visits.
        """
        stmt = (
            select(Visit, User.name.label("barber_name"))
            .join(User, Visit.barber_id == User.id)
            .where(
                Visit.branch_id == branch_id,
                Visit.date >= target_date,
                Visit.status == "scheduled",
            )
            .order_by(Visit.date, Visit.created_at)
        )
        rows = (await self.db.execute(stmt)).all()

        total_upcoming = len(rows)
        confirmed_upcoming = sum(1 for v, _ in rows if v.confirmed)

        unconfirmed_record_ids = [v.yclients_record_id for v, _ in rows if not v.confirmed]
        called_map: dict[int, str] = {}
        if unconfirmed_record_ids:
            cres = await self.db.execute(
                select(AdminCallLog.yclients_record_id, AdminCallLog.result).where(
                    AdminCallLog.branch_id == branch_id,
                    AdminCallLog.call_date == target_date,
                    AdminCallLog.yclients_record_id.in_(unconfirmed_record_ids),
                )
            )
            called_map = {r.yclients_record_id: r.result for r in cres.all()}

        to_call = []
        for visit, barber_name in rows:
            if visit.confirmed:
                continue
            client_name, phone = "Без имени", None
            if visit.client_id:
                c = (
                    await self.db.execute(
                        select(Client.name, Client.phone).where(Client.id == visit.client_id)
                    )
                ).first()
                if c:
                    client_name = c.name or "Без имени"
                    phone = c.phone or None
            to_call.append(
                {
                    "record_id": str(visit.id),
                    "yclients_record_id": visit.yclients_record_id,
                    "client_name": client_name,
                    "phone": phone,
                    "date": str(visit.date),
                    "datetime": str(visit.created_at),
                    "barber_name": barber_name,
                    "called": visit.yclients_record_id in called_map,
                    "result": called_map.get(visit.yclients_record_id),
                }
            )

        to_call_count = len(to_call)
        called_count = sum(1 for x in to_call if x["called"])
        confirmation_rate = (
            round(confirmed_upcoming / total_upcoming * 100) if total_upcoming else 100
        )
        call_progress = round(called_count / to_call_count * 100) if to_call_count else 100

        return {
            "branch_id": str(branch_id),
            "date": str(target_date),
            "to_call": to_call,
            "total_upcoming": total_upcoming,
            "confirmed_upcoming": confirmed_upcoming,
            "confirmation_rate": confirmation_rate,
            "to_call_count": to_call_count,
            "called_count": called_count,
            "call_progress": call_progress,
        }

    async def mark_call(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        admin_id: uuid.UUID,
        yclients_record_id: int,
        result: str,
        call_date: date,
    ) -> None:
        """Log (or update) an admin's call about an upcoming appointment."""
        stmt = pg_insert(AdminCallLog).values(
            id=uuid.uuid4(),
            organization_id=organization_id,
            branch_id=branch_id,
            admin_id=admin_id,
            yclients_record_id=yclients_record_id,
            call_date=call_date,
            result=result,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_admin_call_branch_record_date",
            set_={"result": result, "admin_id": admin_id},
        )
        await self.db.execute(stmt)
        await self.db.commit()

    # ------------------------------------------------------------------
    # DataHeroes quality-control call tasks
    # ------------------------------------------------------------------

    async def get_qc_call_list(self, branch_id: uuid.UUID) -> dict:
        """Quality-control call tasks (synced from DataHeroes) for a branch.

        Pending tasks come first; contacted ones stay visible (faded) for the
        rest of the day. Mirrors the shape of ``get_call_list``'s progress block.
        """
        stmt = (
            select(DHCallTask)
            .where(DHCallTask.branch_id == branch_id)
            .order_by(DHCallTask.status.desc(), DHCallTask.synced_at.desc())
        )
        rows = list((await self.db.execute(stmt)).scalars().all())

        tasks = [
            {
                "task_id": t.dataheroes_task_id,
                "client_name": t.client_name or "Без имени",
                "phone": t.phone or None,
                "reason": t.reason,
                "visit_count": t.visit_count,
                "status": t.status,
                "result": t.result,
            }
            for t in rows
        ]
        total = len(rows)
        contacted_count = sum(1 for t in rows if t.status == "contacted")
        pending_count = total - contacted_count
        progress = round(contacted_count / total * 100) if total else 100

        return {
            "branch_id": str(branch_id),
            "tasks": tasks,
            "total": total,
            "pending_count": pending_count,
            "contacted_count": contacted_count,
            "progress": progress,
        }

    async def mark_qc_call(
        self,
        branch_id: uuid.UUID,
        admin_id: uuid.UUID,
        task_id: str,
        result: str | None = None,
    ) -> dict:
        """Mark a DataHeroes QC task as contacted — locally first, then push.

        The local row is the source of truth: we commit the "contacted" status
        before calling DataHeroes, so a failed push never loses the admin's
        action. Unpushed rows are retried by the periodic sync task.
        """
        row = (
            await self.db.execute(
                select(DHCallTask).where(
                    DHCallTask.branch_id == branch_id,
                    DHCallTask.dataheroes_task_id == task_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return {"ok": False, "error": "not_found"}

        row.status = "contacted"
        row.result = result
        row.contacted_by = admin_id
        row.contacted_at = datetime.now(UTC)
        row.pushed = False
        await self.db.commit()

        pushed = await self._push_qc_contacted(row)
        return {"ok": True, "pushed": pushed}

    async def _push_qc_contacted(self, row: DHCallTask) -> bool:
        """Push a contacted mark to DataHeroes; tolerate failure (retry later)."""
        if not settings.dataheroes_enabled or not row.dh_project_id:
            return False
        from app.integrations.dataheroes.client import DataHeroesClient

        client = DataHeroesClient()
        try:
            await client.mark_contacted(
                communication_id=row.dataheroes_task_id,
                project_id=row.dh_project_id,
                client_id=row.dh_client_id,
            )
            row.pushed = True
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            await logger.aexception(
                "DataHeroes mark-contacted push failed; kept local, will retry",
                branch_id=str(row.branch_id),
                task_id=row.dataheroes_task_id,
            )
            return False
        finally:
            await client.close()

    async def get_history(
        self,
        branch_id: uuid.UUID,
        year: int,
        month: int,
    ) -> dict:
        """Return daily breakdown for a given month."""
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # Daily aggregates — only completed visits count as realized business,
        # so future (scheduled) bookings don't inflate revenue or appear here.
        stmt = (
            select(
                Visit.date,
                sa_func.count().label("records_count"),
                sa_func.coalesce(sa_func.sum(Visit.products_count), 0).label("products_sold"),
                sa_func.coalesce(sa_func.sum(Visit.revenue), 0).label("revenue"),
            )
            .where(
                Visit.branch_id == branch_id,
                Visit.date >= month_start,
                Visit.date <= month_end,
                Visit.status == "completed",
            )
            .group_by(Visit.date)
            .order_by(Visit.date)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        # Confirmed per day — by the YClients confirmation flag (same as Calls).
        confirmed_stmt = (
            select(
                Visit.date,
                sa_func.count().label("confirmed_count"),
            )
            .where(
                Visit.branch_id == branch_id,
                Visit.date >= month_start,
                Visit.date <= month_end,
                Visit.status == "completed",
                Visit.confirmed.is_(True),
            )
            .group_by(Visit.date)
        )
        confirmed_result = await self.db.execute(confirmed_stmt)
        confirmed_map = {r.date: r.confirmed_count for r in confirmed_result.all()}

        days = []
        for row in rows:
            total = row.records_count
            confirmed = confirmed_map.get(row.date, 0)
            rate = round((confirmed / total) * 100) if total > 0 else 0
            days.append(
                {
                    "date": str(row.date),
                    "records_count": total,
                    "products_sold": row.products_sold,
                    "revenue": row.revenue,
                    "confirmed_rate": rate,
                }
            )

        month_label = f"{year}-{month:02d}"
        return {
            "branch_id": str(branch_id),
            "month": month_label,
            "days": days,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_branch(self, branch_id: uuid.UUID) -> Branch | None:
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        return result.scalar_one_or_none()

    async def _count_visits(
        self,
        branch_id: uuid.UUID,
        target_date: date,
        include_pending: bool = False,
        status: str | None = None,
        confirmed: bool | None = None,
    ) -> int:
        stmt = select(sa_func.count()).select_from(Visit).where(
            Visit.branch_id == branch_id,
            Visit.date == target_date,
        )
        if confirmed is not None:
            stmt = stmt.where(Visit.confirmed.is_(confirmed))
        elif status:
            stmt = stmt.where(Visit.status == status)
        elif not include_pending:
            stmt = stmt.where(Visit.status == "completed")
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _sum_products(self, branch_id: uuid.UUID, target_date: date) -> int:
        stmt = select(
            sa_func.coalesce(sa_func.sum(Visit.products_count), 0)
        ).where(
            Visit.branch_id == branch_id,
            Visit.date == target_date,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _birthday_stats(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
    ) -> tuple[int, int]:
        """Return (filled_birthdays, total_clients) for clients who visited this branch."""
        # Get clients who have visited this branch
        client_ids_stmt = (
            select(sa_func.distinct(Visit.client_id))
            .where(
                Visit.branch_id == branch_id,
                Visit.client_id.isnot(None),
            )
        )

        total_stmt = select(sa_func.count()).where(
            Client.organization_id == organization_id,
            Client.id.in_(client_ids_stmt),
        )
        filled_stmt = select(sa_func.count()).where(
            Client.organization_id == organization_id,
            Client.id.in_(client_ids_stmt),
            Client.birthday.isnot(None),
        )

        total = (await self.db.execute(total_stmt)).scalar_one()
        filled = (await self.db.execute(filled_stmt)).scalar_one()
        return filled, total

    async def _unconfirmed_records(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> list[dict]:
        """Find visits scheduled for target_date that are not confirmed."""
        stmt = (
            select(Visit, User.name.label("barber_name"))
            .join(User, Visit.barber_id == User.id)
            .where(
                Visit.branch_id == branch_id,
                Visit.date == target_date,
                Visit.status == "pending",
            )
            .order_by(Visit.created_at)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        records = []
        for visit, barber_name in rows:
            # Get client name
            client_name = "Без имени"
            if visit.client_id:
                client_result = await self.db.execute(
                    select(Client.name).where(Client.id == visit.client_id)
                )
                client_name = client_result.scalar_one_or_none() or "Без имени"

            # Get service name from services JSON
            service_name = "Услуга"
            if visit.services and isinstance(visit.services, list) and len(visit.services) > 0:
                first = visit.services[0]
                if isinstance(first, dict):
                    service_name = first.get("title", "Услуга")

            records.append(
                {
                    "record_id": str(visit.id),
                    "client_name": client_name,
                    "service_name": service_name,
                    "datetime": str(visit.created_at),
                    "barber_name": barber_name,
                }
            )
        return records

    async def _unfilled_birthdays(self, branch_id: uuid.UUID) -> list[dict]:
        """Find clients who visited this branch but have no birthday on file."""
        client_ids_stmt = (
            select(sa_func.distinct(Visit.client_id))
            .where(
                Visit.branch_id == branch_id,
                Visit.client_id.isnot(None),
            )
        )

        stmt = (
            select(Client)
            .where(
                Client.id.in_(client_ids_stmt),
                Client.birthday.is_(None),
            )
            .order_by(Client.name)
            .limit(20)
        )
        result = await self.db.execute(stmt)
        clients = result.scalars().all()

        return [
            {
                "client_id": str(c.id),
                "client_name": c.name or "Без имени",
                "phone": c.phone if c.phone else None,
                "last_visit": str(c.last_visit_at.date()) if c.last_visit_at else None,
            }
            for c in clients
        ]

    async def _unprocessed_checks(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> list[dict]:
        """Find visits today that are not fully processed (status != completed)."""
        stmt = (
            select(Visit, User.name.label("barber_name"))
            .join(User, Visit.barber_id == User.id)
            .where(
                Visit.branch_id == branch_id,
                Visit.date == target_date,
                Visit.status.notin_(["completed", "confirmed"]),
            )
            .order_by(Visit.created_at)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        checks = []
        for visit, barber_name in rows:
            client_name = "Без имени"
            if visit.client_id:
                client_result = await self.db.execute(
                    select(Client.name).where(Client.id == visit.client_id)
                )
                client_name = client_result.scalar_one_or_none() or "Без имени"

            checks.append(
                {
                    "record_id": str(visit.id),
                    "client_name": client_name,
                    "barber_name": barber_name,
                    "amount": visit.revenue,
                    "datetime": str(visit.created_at),
                    "status": visit.status,
                }
            )
        return checks
