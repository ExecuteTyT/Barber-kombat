"""Report generation service.

Generates management reports for the barbershop network:
- Daily revenue by branch and network
- Day-to-day month comparison
- Client statistics (new vs returning)
- Kombat daily standings
- Kombat monthly summary
"""

import uuid
from datetime import date

import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.daily_rating import DailyRating
from app.models.plan import Plan
from app.models.report import Report
from app.models.review import Review
from app.models.user import User, UserRole
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()


class ReportService:
    """Generates and persists management reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public report generators
    # ------------------------------------------------------------------

    async def generate_daily_revenue(
        self,
        organization_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Generate daily revenue report for all branches.

        Returns a dict with per-branch revenue for the day, month-to-date
        totals, plan progress, and network-wide aggregates.
        """
        month_start = target_date.replace(day=1)

        # Load active branches
        branches = await self._get_active_branches(organization_id)

        branch_data: list[dict] = []
        network_today = 0
        network_mtd = 0

        for branch in branches:
            # Revenue today
            revenue_today = await self._sum_revenue(branch.id, target_date, target_date)
            # Revenue month-to-date
            revenue_mtd = await self._sum_revenue(branch.id, month_start, target_date)

            # Plan
            plan = await self._get_plan(branch.id, month_start)
            plan_target = plan.target_amount if plan else 0
            plan_pct = round((revenue_mtd / plan_target) * 100, 1) if plan_target > 0 else 0.0

            # Barbers in shift today
            barbers_in_shift = await self._count_barbers_in_shift(branch.id, target_date)
            barbers_total = await self._count_barbers_total(branch.id)

            branch_data.append(
                {
                    "branch_id": str(branch.id),
                    "name": branch.name,
                    "revenue_today": revenue_today,
                    "revenue_mtd": revenue_mtd,
                    "plan_target": plan_target,
                    "plan_percentage": plan_pct,
                    "barbers_in_shift": barbers_in_shift,
                    "barbers_total": barbers_total,
                }
            )

            network_today += revenue_today
            network_mtd += revenue_mtd

        report_data = {
            "date": str(target_date),
            "branches": branch_data,
            "network_total_today": network_today,
            "network_total_mtd": network_mtd,
        }

        await self._save_report(
            organization_id=organization_id,
            branch_id=None,
            report_type="daily_revenue",
            report_date=target_date,
            data=report_data,
        )

        await logger.ainfo(
            "Daily revenue report generated",
            org_id=str(organization_id),
            date=str(target_date),
            branches=len(branch_data),
        )
        return report_data

    async def generate_day_to_day(
        self,
        organization_id: uuid.UUID,
        target_date: date,
        branch_id: uuid.UUID | None = None,
    ) -> dict:
        """Generate day-to-day comparison across 3 months.

        Compares cumulative revenue day-by-day for the current month,
        previous month, and two months ago.
        """
        current_month_start = target_date.replace(day=1)
        prev_month_start = _prev_month(current_month_start)
        prev_prev_month_start = _prev_month(prev_month_start)

        day_num = target_date.day

        # Get branches to sum over
        if branch_id:
            branch_ids = [branch_id]
        else:
            branches = await self._get_active_branches(organization_id)
            branch_ids = [b.id for b in branches]

        # Build cumulative data for each month
        current_cumulative = await self._daily_cumulative(branch_ids, current_month_start, day_num)
        prev_cumulative = await self._daily_cumulative(branch_ids, prev_month_start, day_num)
        prev_prev_cumulative = await self._daily_cumulative(
            branch_ids, prev_prev_month_start, day_num
        )

        # Comparison percentages
        current_total = current_cumulative[-1]["amount"] if current_cumulative else 0
        prev_total = prev_cumulative[-1]["amount"] if prev_cumulative else 0
        prev_prev_total = prev_prev_cumulative[-1]["amount"] if prev_prev_cumulative else 0

        vs_prev = _pct_change(current_total, prev_total)
        vs_prev_prev = _pct_change(current_total, prev_prev_total)

        report_data = {
            "branch_id": str(branch_id) if branch_id else None,
            "period_end": str(target_date),
            "current_month": {
                "name": _month_label(current_month_start),
                "daily_cumulative": current_cumulative,
            },
            "prev_month": {
                "name": _month_label(prev_month_start),
                "daily_cumulative": prev_cumulative,
            },
            "prev_prev_month": {
                "name": _month_label(prev_prev_month_start),
                "daily_cumulative": prev_prev_cumulative,
            },
            "comparison": {
                "vs_prev": vs_prev,
                "vs_prev_prev": vs_prev_prev,
            },
        }

        await self._save_report(
            organization_id=organization_id,
            branch_id=branch_id,
            report_type="day_to_day",
            report_date=target_date,
            data=report_data,
        )

        await logger.ainfo(
            "Day-to-day report generated",
            org_id=str(organization_id),
            date=str(target_date),
            branch_id=str(branch_id) if branch_id else "network",
        )
        return report_data

    async def generate_clients_report(
        self,
        organization_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Generate client statistics report (new vs returning)."""
        month_start = target_date.replace(day=1)
        branches = await self._get_active_branches(organization_id)

        branch_data: list[dict] = []
        network_new_mtd = 0
        network_returning_mtd = 0
        network_total_mtd = 0

        for branch in branches:
            # Today
            new_today = await self._count_new_clients(
                branch.id, organization_id, target_date, target_date
            )
            total_today = await self._count_unique_clients(branch.id, target_date, target_date)
            returning_today = total_today - new_today

            # Month-to-date
            new_mtd = await self._count_new_clients(
                branch.id, organization_id, month_start, target_date
            )
            total_mtd = await self._count_unique_clients(branch.id, month_start, target_date)
            returning_mtd = total_mtd - new_mtd

            branch_data.append(
                {
                    "branch_id": str(branch.id),
                    "name": branch.name,
                    "new_clients_today": new_today,
                    "returning_clients_today": returning_today,
                    "total_today": total_today,
                    "new_clients_mtd": new_mtd,
                    "returning_clients_mtd": returning_mtd,
                    "total_mtd": total_mtd,
                }
            )

            network_new_mtd += new_mtd
            network_returning_mtd += returning_mtd
            network_total_mtd += total_mtd

        report_data = {
            "date": str(target_date),
            "branches": branch_data,
            "network_new_mtd": network_new_mtd,
            "network_returning_mtd": network_returning_mtd,
            "network_total_mtd": network_total_mtd,
        }

        await self._save_report(
            organization_id=organization_id,
            branch_id=None,
            report_type="clients",
            report_date=target_date,
            data=report_data,
        )

        await logger.ainfo(
            "Clients report generated",
            org_id=str(organization_id),
            date=str(target_date),
        )
        return report_data

    async def generate_kombat_daily(
        self,
        organization_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Generate Barber Kombat daily standings from DailyRating."""
        branches = await self._get_active_branches(organization_id)

        branch_standings: list[dict] = []
        for branch in branches:
            ratings = await self._get_daily_ratings(branch.id, target_date)
            standings = [
                {
                    "barber_id": str(r.barber_id),
                    "name": name,
                    "rank": r.rank,
                    "total_score": r.total_score,
                    "revenue": r.revenue,
                    "revenue_score": r.revenue_score,
                    "cs_value": r.cs_value,
                    "cs_score": r.cs_score,
                    "products_count": r.products_count,
                    "products_score": r.products_score,
                    "extras_count": r.extras_count,
                    "extras_score": r.extras_score,
                    "reviews_avg": r.reviews_avg,
                    "reviews_score": r.reviews_score,
                }
                for r, name in ratings
            ]

            branch_standings.append(
                {
                    "branch_id": str(branch.id),
                    "name": branch.name,
                    "standings": standings,
                }
            )

        report_data = {
            "date": str(target_date),
            "branches": branch_standings,
        }

        await self._save_report(
            organization_id=organization_id,
            branch_id=None,
            report_type="kombat_daily",
            report_date=target_date,
            data=report_data,
        )

        await logger.ainfo(
            "Kombat daily report generated",
            org_id=str(organization_id),
            date=str(target_date),
        )
        return report_data

    async def generate_kombat_monthly(
        self,
        organization_id: uuid.UUID,
        month: date,
    ) -> dict:
        """Generate Barber Kombat monthly summary.

        Aggregates DailyRating entries for the entire month and ranks
        barbers by cumulative total_score.
        """
        month_start = month.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        branches = await self._get_active_branches(organization_id)

        branch_summaries: list[dict] = []
        for branch in branches:
            # Aggregate scores for the month
            stmt = (
                select(
                    DailyRating.barber_id,
                    User.name,
                    sa_func.count(DailyRating.id).label("days_worked"),
                    sa_func.sum(DailyRating.revenue).label("total_revenue"),
                    sa_func.avg(DailyRating.total_score).label("avg_score"),
                    sa_func.count(sa_func.nullif(DailyRating.rank, 0))
                    .filter(DailyRating.rank == 1)
                    .label("wins"),
                )
                .join(User, User.id == DailyRating.barber_id)
                .where(
                    DailyRating.branch_id == branch.id,
                    DailyRating.date >= month_start,
                    DailyRating.date < month_end,
                )
                .group_by(DailyRating.barber_id, User.name)
                .order_by(sa_func.avg(DailyRating.total_score).desc())
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            standings = [
                {
                    "barber_id": str(row.barber_id),
                    "name": row.name,
                    "days_worked": row.days_worked,
                    "total_revenue": row.total_revenue or 0,
                    "avg_score": round(row.avg_score, 2) if row.avg_score else 0.0,
                    "wins": row.wins or 0,
                    "rank": idx + 1,
                }
                for idx, row in enumerate(rows)
            ]

            branch_summaries.append(
                {
                    "branch_id": str(branch.id),
                    "name": branch.name,
                    "standings": standings,
                }
            )

        report_data = {
            "month": str(month_start),
            "branches": branch_summaries,
        }

        await self._save_report(
            organization_id=organization_id,
            branch_id=None,
            report_type="kombat_monthly",
            report_date=month_start,
            data=report_data,
        )

        await logger.ainfo(
            "Kombat monthly report generated",
            org_id=str(organization_id),
            month=str(month_start),
        )
        return report_data

    async def generate_branch_analytics(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> dict:
        """Generate comprehensive analytics for a single branch.

        Composes revenue, client, shift, top-barber, and aggregate data
        into a single response for the chef analytics dashboard.
        """
        month_start = target_date.replace(day=1)

        # Branch name
        branch = await self._get_branch(branch_id)
        branch_name = branch.name if branch else "Unknown"

        # Revenue
        revenue_today = await self._sum_revenue(branch_id, target_date, target_date)
        revenue_mtd = await self._sum_revenue(branch_id, month_start, target_date)

        # Plan
        plan = await self._get_plan(branch_id, month_start)
        plan_target = plan.target_amount if plan else 0
        plan_pct = round((revenue_mtd / plan_target) * 100, 1) if plan_target > 0 else 0.0

        # Visits count (for avg check)
        visits_today = await self._count_visits(branch_id, target_date, target_date)
        visits_mtd = await self._count_visits(branch_id, month_start, target_date)
        avg_check_today = revenue_today // visits_today if visits_today > 0 else 0
        avg_check_mtd = revenue_mtd // visits_mtd if visits_mtd > 0 else 0

        # Clients
        clients_today = await self._count_unique_clients(branch_id, target_date, target_date)
        new_clients_mtd = await self._count_new_clients(
            branch_id, organization_id, month_start, target_date
        )
        total_clients_mtd = await self._count_unique_clients(branch_id, month_start, target_date)
        returning_clients_mtd = total_clients_mtd - new_clients_mtd

        # Shift
        barbers_in_shift = await self._count_barbers_in_shift(branch_id, target_date)
        barbers_total = await self._count_barbers_total(branch_id)

        # Top barbers (monthly)
        top_barbers = await self._get_top_barbers(branch_id, month_start, target_date)

        # Aggregates
        total_products_mtd = await self._sum_products(branch_id, month_start, target_date)
        total_extras_mtd = await self._sum_extras(branch_id, month_start, target_date)
        avg_review_score = await self._avg_review_score(branch_id, month_start, target_date)

        return {
            "branch_id": str(branch_id),
            "branch_name": branch_name,
            "date": str(target_date),
            "revenue_today": revenue_today,
            "revenue_mtd": revenue_mtd,
            "plan_target": plan_target,
            "plan_percentage": plan_pct,
            "avg_check_today": avg_check_today,
            "avg_check_mtd": avg_check_mtd,
            "visits_today": visits_today,
            "visits_mtd": visits_mtd,
            "clients_today": clients_today,
            "new_clients_mtd": new_clients_mtd,
            "returning_clients_mtd": returning_clients_mtd,
            "total_clients_mtd": total_clients_mtd,
            "barbers_in_shift": barbers_in_shift,
            "barbers_total": barbers_total,
            "top_barbers": top_barbers,
            "total_products_mtd": total_products_mtd,
            "total_extras_mtd": total_extras_mtd,
            "avg_review_score": avg_review_score,
        }

    # ------------------------------------------------------------------
    # Report retrieval (for API)
    # ------------------------------------------------------------------

    async def get_report(
        self,
        organization_id: uuid.UUID,
        report_type: str,
        report_date: date,
        branch_id: uuid.UUID | None = None,
    ) -> Report | None:
        """Retrieve a single report by type, date, and optional branch."""
        stmt = select(Report).where(
            Report.organization_id == organization_id,
            Report.type == report_type,
            Report.date == report_date,
        )
        if branch_id is not None:
            stmt = stmt.where(Report.branch_id == branch_id)
        else:
            stmt = stmt.where(Report.branch_id.is_(None))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_reports(
        self,
        organization_id: uuid.UUID,
        report_type: str,
        date_from: date,
        date_to: date,
        branch_id: uuid.UUID | None = None,
    ) -> list[Report]:
        """List reports by type and date range."""
        stmt = (
            select(Report)
            .where(
                Report.organization_id == organization_id,
                Report.type == report_type,
                Report.date >= date_from,
                Report.date <= date_to,
            )
            .order_by(Report.date.desc())
        )
        if branch_id is not None:
            stmt = stmt.where(Report.branch_id == branch_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_active_branches(self, organization_id: uuid.UUID) -> list[Branch]:
        """Load all active branches for an organization."""
        result = await self.db.execute(
            select(Branch).where(
                Branch.organization_id == organization_id,
                Branch.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _sum_revenue(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Sum completed visit revenue for a branch in a date range."""
        stmt = select(sa_func.coalesce(sa_func.sum(Visit.revenue), 0)).where(
            Visit.branch_id == branch_id,
            Visit.date >= date_from,
            Visit.date <= date_to,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _get_plan(self, branch_id: uuid.UUID, month_start: date) -> Plan | None:
        """Load the revenue plan for a branch/month."""
        result = await self.db.execute(
            select(Plan).where(
                Plan.branch_id == branch_id,
                Plan.month == month_start,
            )
        )
        return result.scalar_one_or_none()

    async def _count_barbers_in_shift(self, branch_id: uuid.UUID, target_date: date) -> int:
        """Count barbers who had at least one visit today."""
        stmt = select(sa_func.count(sa_func.distinct(Visit.barber_id))).where(
            Visit.branch_id == branch_id,
            Visit.date == target_date,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _count_barbers_total(self, branch_id: uuid.UUID) -> int:
        """Count total active barbers in a branch."""
        stmt = select(sa_func.count()).where(
            User.branch_id == branch_id,
            User.role == UserRole.BARBER,
            User.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _count_new_clients(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Count clients whose first-ever visit falls within the date range.

        A "new client" is defined by their phone number not appearing in any
        visit record prior to the date range.  We use a subquery to find
        client_ids that had visits before ``date_from``.
        """
        # Subquery: clients with visits before date_from
        prev_clients = (
            select(Visit.client_id)
            .where(
                Visit.organization_id == organization_id,
                Visit.date < date_from,
                Visit.status == "completed",
                Visit.client_id.isnot(None),
            )
            .distinct()
            .scalar_subquery()
        )

        stmt = select(sa_func.count(sa_func.distinct(Visit.client_id))).where(
            Visit.branch_id == branch_id,
            Visit.date >= date_from,
            Visit.date <= date_to,
            Visit.status == "completed",
            Visit.client_id.isnot(None),
            Visit.client_id.notin_(prev_clients),
        )

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _count_unique_clients(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Count unique clients with completed visits in a date range."""
        stmt = select(sa_func.count(sa_func.distinct(Visit.client_id))).where(
            Visit.branch_id == branch_id,
            Visit.date >= date_from,
            Visit.date <= date_to,
            Visit.status == "completed",
            Visit.client_id.isnot(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _daily_cumulative(
        self,
        branch_ids: list[uuid.UUID],
        month_start: date,
        max_day: int,
    ) -> list[dict]:
        """Build daily cumulative revenue array for a list of branches.

        Returns a list like ``[{"day": 1, "amount": X}, ...]`` up to
        ``max_day``.
        """
        cumulative: list[dict] = []
        running_total = 0

        for day_num in range(1, max_day + 1):
            target = month_start.replace(day=day_num)
            day_revenue = 0
            for bid in branch_ids:
                day_revenue += await self._sum_revenue(bid, target, target)
            running_total += day_revenue
            cumulative.append({"day": day_num, "amount": running_total})

        return cumulative

    async def _get_daily_ratings(
        self,
        branch_id: uuid.UUID,
        target_date: date,
    ) -> list[tuple]:
        """Load DailyRating rows with barber name for a branch/date."""
        stmt = (
            select(DailyRating, User.name)
            .join(User, User.id == DailyRating.barber_id)
            .where(
                DailyRating.branch_id == branch_id,
                DailyRating.date == target_date,
            )
            .order_by(DailyRating.rank)
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    async def _get_branch(self, branch_id: uuid.UUID) -> Branch | None:
        """Load a single branch by ID."""
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        return result.scalar_one_or_none()

    async def _count_visits(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Count completed visits for a branch in a date range."""
        stmt = select(sa_func.count()).where(
            Visit.branch_id == branch_id,
            Visit.date >= date_from,
            Visit.date <= date_to,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _sum_products(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Sum products_count for completed visits in a date range."""
        stmt = select(sa_func.coalesce(sa_func.sum(Visit.products_count), 0)).where(
            Visit.branch_id == branch_id,
            Visit.date >= date_from,
            Visit.date <= date_to,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _sum_extras(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> int:
        """Sum extras_count for completed visits in a date range."""
        stmt = select(sa_func.coalesce(sa_func.sum(Visit.extras_count), 0)).where(
            Visit.branch_id == branch_id,
            Visit.date >= date_from,
            Visit.date <= date_to,
            Visit.status == "completed",
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _avg_review_score(
        self,
        branch_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> float | None:
        """Average review rating for a branch in a date range."""
        stmt = select(sa_func.avg(Review.rating)).where(
            Review.branch_id == branch_id,
            Review.created_at >= date_from,
            Review.created_at <= date_to,
        )
        result = await self.db.execute(stmt)
        avg = result.scalar_one()
        return round(avg, 2) if avg is not None else None

    async def _get_top_barbers(
        self,
        branch_id: uuid.UUID,
        month_start: date,
        month_end: date,
    ) -> list[dict]:
        """Get top barbers by revenue for the month from DailyRating data."""
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)

        stmt = (
            select(
                DailyRating.barber_id,
                User.name,
                sa_func.coalesce(sa_func.sum(DailyRating.revenue), 0).label("total_revenue"),
                sa_func.avg(DailyRating.total_score).label("avg_score"),
                sa_func.count(DailyRating.id).filter(DailyRating.rank == 1).label("wins"),
                sa_func.count(DailyRating.id).label("days_worked"),
            )
            .join(User, User.id == DailyRating.barber_id)
            .where(
                DailyRating.branch_id == branch_id,
                DailyRating.date >= month_start,
                DailyRating.date < next_month,
            )
            .group_by(DailyRating.barber_id, User.name)
            .order_by(sa_func.sum(DailyRating.revenue).desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "barber_id": str(row.barber_id),
                "name": row.name,
                "revenue": row.total_revenue or 0,
                "avg_score": round(row.avg_score, 2) if row.avg_score else 0.0,
                "wins": row.wins or 0,
                "days_worked": row.days_worked or 0,
            }
            for row in rows
        ]

    async def _save_report(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        report_type: str,
        report_date: date,
        data: dict,
    ) -> None:
        """Persist report data via UPSERT (replace if same type+date+branch)."""
        values = {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            "branch_id": branch_id,
            "type": report_type,
            "date": report_date,
            "data": data,
            "delivered_telegram": False,
        }

        stmt = pg_insert(Report).values(**values)

        if branch_id is None:
            # Use partial unique index for NULL branch_id
            stmt = stmt.on_conflict_do_update(
                index_elements=["organization_id", "type", "date"],
                index_where=Report.branch_id.is_(None),
                set_={
                    "data": stmt.excluded.data,
                    "delivered_telegram": False,
                },
            )
        else:
            # Use partial unique index for non-NULL branch_id
            stmt = stmt.on_conflict_do_update(
                index_elements=["organization_id", "branch_id", "type", "date"],
                index_where=Report.branch_id.isnot(None),
                set_={
                    "data": stmt.excluded.data,
                    "delivered_telegram": False,
                },
            )

        await self.db.execute(stmt)
        await self.db.commit()


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _prev_month(d: date) -> date:
    """Return the first day of the previous month."""
    if d.month == 1:
        return d.replace(year=d.year - 1, month=12, day=1)
    return d.replace(month=d.month - 1, day=1)


def _month_label(d: date) -> str:
    """Human-readable month label in Russian."""
    month_names = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }
    return f"{month_names[d.month]} {d.year}"


def _pct_change(current: int, previous: int) -> str:
    """Format percentage change as a signed string."""
    if previous == 0:
        if current > 0:
            return "+100.0%"
        return "0.0%"
    pct = ((current - previous) / previous) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"
