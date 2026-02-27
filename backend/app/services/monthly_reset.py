"""Monthly Reset Service.

Handles the end-of-month lifecycle:
1. Finalize daily_ratings — determine monthly champions per branch
2. Freeze prize funds — record final amounts in a kombat_monthly report
3. Create new pvr_records with zeroes for every active barber
4. Copy plans to the new month (if targets are set)

Runs on the 1st of each month at 00:05 (via Celery beat) or manually via CLI.
"""

import calendar
import uuid
from datetime import date

import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.daily_rating import DailyRating
from app.models.organization import Organization
from app.models.plan import Plan
from app.models.pvr_record import PVRRecord
from app.models.report import Report
from app.models.user import User, UserRole

logger = structlog.stdlib.get_logger()


class MonthlyResetService:
    """Performs the monthly reset for a single organization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def reset_organization(self, org_id: uuid.UUID, month: date) -> dict:
        """Run the full monthly reset for an organization.

        Args:
            org_id: Organization UUID.
            month: The month being finalized (1st day, e.g. 2026-01-01).
                   New records are created for the *next* month.

        Returns:
            Summary dict with counts.
        """
        month_start = month.replace(day=1)
        next_month = _next_month(month_start)

        # 1. Get all active branches
        branches = await self._get_active_branches(org_id)

        champions_count = 0
        pvr_records_created = 0
        plans_copied = 0

        for branch in branches:
            # 2. Finalize ratings — determine the champion
            champion = await self._finalize_branch_ratings(org_id, branch.id, month_start)
            if champion:
                champions_count += 1

            # 3. Generate kombat_monthly report (freeze prize fund + standings)
            await self._save_monthly_report(org_id, branch.id, month_start, champion)

        # 4. Create new PVR records with zeroes for every active barber
        pvr_records_created = await self._create_new_pvr_records(org_id, next_month)

        # 5. Copy plans to next month (carry over target_amount)
        plans_copied = await self._copy_plans(org_id, month_start, next_month)

        await self.db.commit()

        summary = {
            "organization_id": str(org_id),
            "finalized_month": str(month_start),
            "new_month": str(next_month),
            "branches": len(branches),
            "champions": champions_count,
            "pvr_records_created": pvr_records_created,
            "plans_copied": plans_copied,
        }
        await logger.ainfo("Monthly reset completed", **summary)
        return summary

    async def reset_all_organizations(self, month: date) -> dict:
        """Run monthly reset for every active organization.

        Args:
            month: Month being finalized.

        Returns:
            Aggregate summary.
        """
        result = await self.db.execute(select(Organization).where(Organization.is_active.is_(True)))
        orgs = result.scalars().all()

        orgs_processed = 0
        errors = 0

        for org in orgs:
            try:
                await self.reset_organization(org.id, month)
                orgs_processed += 1
            except Exception:
                errors += 1
                await logger.aexception(
                    "Monthly reset failed for organization",
                    org_id=str(org.id),
                    month=str(month),
                )

        return {
            "month": str(month.replace(day=1)),
            "orgs_processed": orgs_processed,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    async def _get_active_branches(self, org_id: uuid.UUID) -> list[Branch]:
        """Get all active branches for an organization."""
        result = await self.db.execute(
            select(Branch).where(
                Branch.organization_id == org_id,
                Branch.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _finalize_branch_ratings(
        self,
        org_id: uuid.UUID,
        branch_id: uuid.UUID,
        month_start: date,
    ) -> dict | None:
        """Determine the monthly champion for a branch.

        Champion = barber with the most rank==1 days (wins).
        Tiebreaker: highest total score sum for the month.

        Returns a dict with champion info or None if no ratings exist.
        """
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)

        # Count wins (days at rank 1) per barber
        wins_stmt = (
            select(
                DailyRating.barber_id,
                sa_func.count().label("wins"),
                sa_func.sum(DailyRating.total_score).label("total_score"),
            )
            .where(
                DailyRating.branch_id == branch_id,
                DailyRating.date >= month_start,
                DailyRating.date <= month_end,
                DailyRating.rank == 1,
            )
            .group_by(DailyRating.barber_id)
            .order_by(sa_func.count().desc(), sa_func.sum(DailyRating.total_score).desc())
        )

        result = await self.db.execute(wins_stmt)
        rows = result.all()

        if not rows:
            return None

        champion_row = rows[0]
        champion_barber_id = champion_row.barber_id
        champion_wins = champion_row.wins
        champion_total = float(champion_row.total_score)

        # Get barber name
        barber_result = await self.db.execute(
            select(User.name).where(User.id == champion_barber_id)
        )
        champion_name = barber_result.scalar_one_or_none() or "Unknown"

        # Build full standings (all barbers with wins)
        standings = []
        for row in rows:
            name_result = await self.db.execute(select(User.name).where(User.id == row.barber_id))
            name = name_result.scalar_one_or_none() or "Unknown"
            standings.append(
                {
                    "barber_id": str(row.barber_id),
                    "name": name,
                    "wins": row.wins,
                    "total_score": round(float(row.total_score), 2),
                }
            )

        return {
            "barber_id": str(champion_barber_id),
            "name": champion_name,
            "wins": champion_wins,
            "total_score": round(champion_total, 2),
            "standings": standings,
        }

    async def _save_monthly_report(
        self,
        org_id: uuid.UUID,
        branch_id: uuid.UUID,
        month_start: date,
        champion: dict | None,
    ) -> None:
        """Save the kombat_monthly report for a branch."""
        # Calculate final prize fund from monthly revenue
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)

        revenue_stmt = select(sa_func.coalesce(sa_func.sum(DailyRating.revenue), 0)).where(
            DailyRating.branch_id == branch_id,
            DailyRating.date >= month_start,
            DailyRating.date <= month_end,
        )
        revenue_result = await self.db.execute(revenue_stmt)
        total_revenue: int = revenue_result.scalar_one()

        report_data = {
            "branch_id": str(branch_id),
            "month": str(month_start),
            "total_revenue": total_revenue,
            "champion": champion,
        }

        report = Report(
            organization_id=org_id,
            branch_id=branch_id,
            type="kombat_monthly",
            date=month_start,
            data=report_data,
        )
        self.db.add(report)

    async def _create_new_pvr_records(
        self,
        org_id: uuid.UUID,
        new_month: date,
    ) -> int:
        """Create empty PVR records for every active barber in the org.

        Returns the number of records created.
        """
        # Get all active barbers
        result = await self.db.execute(
            select(User).where(
                User.organization_id == org_id,
                User.role == UserRole.BARBER,
                User.is_active.is_(True),
            )
        )
        barbers = result.scalars().all()

        created = 0
        for barber in barbers:
            # Check if a record already exists (idempotency)
            existing = await self.db.execute(
                select(PVRRecord.id).where(
                    PVRRecord.barber_id == barber.id,
                    PVRRecord.month == new_month,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            record = PVRRecord(
                organization_id=org_id,
                barber_id=barber.id,
                month=new_month,
                cumulative_revenue=0,
                current_threshold=None,
                bonus_amount=0,
                thresholds_reached=[],
            )
            self.db.add(record)
            created += 1

        return created

    async def _copy_plans(
        self,
        org_id: uuid.UUID,
        old_month: date,
        new_month: date,
    ) -> int:
        """Copy plan targets from old_month to new_month for all branches.

        Only copies if a plan existed for old_month and doesn't yet exist
        for new_month. current_amount and percentage are set to 0.

        Returns the number of plans copied.
        """
        result = await self.db.execute(
            select(Plan).where(
                Plan.organization_id == org_id,
                Plan.month == old_month,
            )
        )
        old_plans = result.scalars().all()

        copied = 0
        for old_plan in old_plans:
            # Check idempotency
            existing = await self.db.execute(
                select(Plan.id).where(
                    Plan.branch_id == old_plan.branch_id,
                    Plan.month == new_month,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            new_plan = Plan(
                organization_id=org_id,
                branch_id=old_plan.branch_id,
                month=new_month,
                target_amount=old_plan.target_amount,
                current_amount=0,
                percentage=0.0,
                forecast_amount=None,
            )
            self.db.add(new_plan)
            copied += 1

        return copied


def _next_month(d: date) -> date:
    """Return the 1st day of the next month."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)
