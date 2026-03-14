"""Plan Service — CRUD, progress tracking, forecasting, and notifications.

Manages monthly revenue plans for branches. Integrates with SyncService
to update progress after each data sync.
"""

import calendar
import json
import uuid
from datetime import UTC, date, datetime, timedelta

import redis.asyncio as aioredis
import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.plan import Plan
from app.models.visit import Visit

logger = structlog.stdlib.get_logger()

# If actual percentage is more than 15 pp below expected, fire a warning.
_DEVIATION_THRESHOLD_PP = 15.0

# Approximate fraction of days that are working shifts.
_WORKING_DAYS_RATIO = 0.6


class PlanService:
    """Manages revenue plans and progress tracking."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    # --- CRUD ---

    async def upsert_plan(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        month: date,
        target_amount: int,
    ) -> Plan:
        """Create or update a plan for a branch/month pair.

        Uses UPSERT on the (branch_id, month) unique constraint.
        """
        month_start = month.replace(day=1)

        values: dict = {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            "branch_id": branch_id,
            "month": month_start,
            "target_amount": target_amount,
            "current_amount": 0,
            "percentage": 0.0,
            "forecast_amount": None,
        }

        stmt = pg_insert(Plan).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_plans_branch_month",
            set_={
                "target_amount": stmt.excluded.target_amount,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

        # Immediately recalculate progress for the new/updated plan
        await self.update_progress(branch_id, month_start)

        return await self._get_plan(branch_id, month_start)

    async def get_plan(
        self,
        branch_id: uuid.UUID,
        month: date | None = None,
    ) -> Plan | None:
        """Get a plan for a branch. Defaults to current month."""
        month_start = (month or date.today()).replace(day=1)
        return await self._get_plan(branch_id, month_start)

    async def get_plan_with_details(
        self,
        branch_id: uuid.UUID,
        organization_id: uuid.UUID,
        month: date | None = None,
    ) -> dict | None:
        """Get plan with computed fields (required_daily, is_behind, etc.)."""
        month_start = (month or date.today()).replace(day=1)
        plan = await self._get_plan(branch_id, month_start)
        if plan is None:
            return None

        branch = await self._get_branch(branch_id)
        branch_name = branch.name if branch else "Unknown"

        return self._format_plan(plan, branch_name)

    async def get_network_plans(
        self,
        organization_id: uuid.UUID,
        month: date | None = None,
    ) -> dict:
        """Get plans for all active branches in the organization.

        Branches without a plan for the given month are included with
        target_amount=0 so the frontend can display them and allow the
        owner to set a plan.
        """
        month_start = (month or date.today()).replace(day=1)

        # Fetch all active branches
        branches_result = await self.db.execute(
            select(Branch)
            .where(
                Branch.organization_id == organization_id,
                Branch.is_active.is_(True),
            )
            .order_by(Branch.name)
        )
        all_branches = branches_result.scalars().all()

        # Fetch existing plans for this month
        plans_result = await self.db.execute(
            select(Plan).where(
                Plan.organization_id == organization_id,
                Plan.month == month_start,
            )
        )
        plans_by_branch: dict[uuid.UUID, Plan] = {
            p.branch_id: p for p in plans_result.scalars().all()
        }

        plans = []
        total_target = 0
        total_current = 0

        for branch in all_branches:
            plan = plans_by_branch.get(branch.id)
            if plan:
                plans.append(
                    {
                        "branch_id": plan.branch_id,
                        "branch_name": branch.name,
                        "target_amount": plan.target_amount,
                        "current_amount": plan.current_amount,
                        "percentage": plan.percentage,
                        "forecast_amount": plan.forecast_amount,
                    }
                )
                total_target += plan.target_amount
                total_current += plan.current_amount
            else:
                plans.append(
                    {
                        "branch_id": branch.id,
                        "branch_name": branch.name,
                        "target_amount": 0,
                        "current_amount": 0,
                        "percentage": 0.0,
                        "forecast_amount": None,
                    }
                )

        total_pct = (total_current / total_target * 100) if total_target > 0 else 0.0

        return {
            "month": f"{month_start.year}-{month_start.month:02d}",
            "plans": plans,
            "total_target": total_target,
            "total_current": total_current,
            "total_percentage": round(total_pct, 1),
        }

    # --- Progress update (called after sync) ---

    async def update_progress(
        self,
        branch_id: uuid.UUID,
        month: date | None = None,
    ) -> Plan | None:
        """Recalculate plan progress from completed visits.

        Pipeline:
        1. Load the plan for this branch/month
        2. Sum completed visit revenue for the month
        3. Calculate percentage, forecast, required daily
        4. Check deviation and send warning if needed
        5. Publish WebSocket update
        """
        month_start = (month or date.today()).replace(day=1)
        plan = await self._get_plan(branch_id, month_start)
        if plan is None:
            return None

        # 1. Sum completed revenue for the month
        current_amount = await self._sum_revenue(branch_id, month_start)

        # 2. Calculate percentage
        percentage = (current_amount / plan.target_amount * 100) if plan.target_amount > 0 else 0.0

        # 3. Forecast (linear extrapolation)
        today = date.today()
        days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]

        # Only forecast if we're in or past the plan month
        if today >= month_start:
            days_passed = min((today - month_start).days + 1, days_in_month)
        else:
            days_passed = 0

        forecast_amount = None
        if days_passed > 0:
            daily_avg = current_amount / days_passed
            forecast_amount = int(daily_avg * days_in_month)

        # 4. Update plan record
        plan.current_amount = current_amount
        plan.percentage = round(percentage, 1)
        plan.forecast_amount = forecast_amount
        await self.db.commit()

        # 5. Check deviation and notify
        await self._check_deviation(plan, days_passed, days_in_month, branch_id)

        # 6. Publish WebSocket update
        await self._publish_plan_update(plan)

        await logger.ainfo(
            "Plan progress updated",
            branch_id=str(branch_id),
            month=str(month_start),
            current=current_amount,
            target=plan.target_amount,
            pct=plan.percentage,
            forecast=forecast_amount,
        )

        return plan

    async def update_progress_all_branches(
        self,
        organization_id: uuid.UUID,
        month: date | None = None,
    ) -> int:
        """Update plan progress for all branches in an organization.

        Returns the number of plans updated.
        """
        month_start = (month or date.today()).replace(day=1)

        result = await self.db.execute(
            select(Plan.branch_id).where(
                Plan.organization_id == organization_id,
                Plan.month == month_start,
            )
        )
        branch_ids = result.scalars().all()

        updated = 0
        for bid in branch_ids:
            plan = await self.update_progress(bid, month_start)
            if plan is not None:
                updated += 1

        return updated

    # --- Private helpers ---

    async def _get_plan(self, branch_id: uuid.UUID, month: date) -> Plan | None:
        """Load a plan by branch + month."""
        result = await self.db.execute(
            select(Plan).where(
                Plan.branch_id == branch_id,
                Plan.month == month,
            )
        )
        return result.scalar_one_or_none()

    async def _get_branch(self, branch_id: uuid.UUID) -> Branch | None:
        """Load a branch by id."""
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        return result.scalar_one_or_none()

    async def _sum_revenue(self, branch_id: uuid.UUID, month_start: date) -> int:
        """Sum revenue from completed visits for a branch in the given month."""
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        today = date.today()
        # Don't sum beyond today
        effective_end = min(month_end, today + timedelta(days=1))

        stmt = select(sa_func.coalesce(sa_func.sum(Visit.revenue), 0)).where(
            Visit.branch_id == branch_id,
            Visit.date >= month_start,
            Visit.date < effective_end,
            Visit.status == "completed",
        )

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def _check_deviation(
        self,
        plan: Plan,
        days_passed: int,
        days_in_month: int,
        branch_id: uuid.UUID,
    ) -> None:
        """Send a warning notification if plan execution is lagging."""
        if days_passed <= 0 or days_in_month <= 0:
            return

        expected_pct = (days_passed / days_in_month) * 100
        actual_pct = plan.percentage

        if actual_pct < expected_pct - _DEVIATION_THRESHOLD_PP:
            branch = await self._get_branch(branch_id)
            branch_name = branch.name if branch else "Unknown"

            payload = {
                "type": "plan_warning",
                "branch_id": str(branch_id),
                "branch_name": branch_name,
                "actual_percentage": round(actual_pct, 1),
                "expected_percentage": round(expected_pct, 1),
                "message": (
                    f"Филиал {branch_name}: выполнение плана {actual_pct:.0f}%, "
                    f"ожидалось {expected_pct:.0f}%"
                ),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await self.redis.publish(
                f"ws:org:{plan.organization_id}",
                json.dumps(payload),
            )
            await logger.awarning(
                "Plan deviation warning",
                branch_id=str(branch_id),
                branch_name=branch_name,
                actual_pct=actual_pct,
                expected_pct=expected_pct,
            )

    async def _publish_plan_update(self, plan: Plan) -> None:
        """Publish plan_update event via Redis Pub/Sub."""
        payload = {
            "type": "plan_update",
            "branch_id": str(plan.branch_id),
            "percentage": plan.percentage,
            "current_amount": plan.current_amount,
            "target_amount": plan.target_amount,
            "forecast_amount": plan.forecast_amount,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self.redis.publish(
            f"ws:org:{plan.organization_id}",
            json.dumps(payload),
        )

    @staticmethod
    def _format_plan(plan: Plan, branch_name: str) -> dict:
        """Format a plan for the detailed API response."""
        today = date.today()
        month_start = plan.month
        days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=days_in_month)

        if today >= month_start:
            days_passed = min((today - month_start).days + 1, days_in_month)
        else:
            days_passed = 0

        days_left = max((month_end - today).days, 0)

        # Required daily revenue to hit target
        remaining = plan.target_amount - plan.current_amount
        working_days_left = int(days_left * _WORKING_DAYS_RATIO)
        required_daily = (
            int(remaining / working_days_left) if working_days_left > 0 and remaining > 0 else 0
        )

        # Deviation check
        expected_pct = (days_passed / days_in_month * 100) if days_in_month > 0 else 0.0
        is_behind = plan.percentage < (expected_pct - _DEVIATION_THRESHOLD_PP)

        return {
            "id": plan.id,
            "branch_id": plan.branch_id,
            "branch_name": branch_name,
            "month": f"{month_start.year}-{month_start.month:02d}",
            "target_amount": plan.target_amount,
            "current_amount": plan.current_amount,
            "percentage": plan.percentage,
            "forecast_amount": plan.forecast_amount,
            "required_daily": required_daily if required_daily > 0 else None,
            "days_passed": days_passed,
            "days_in_month": days_in_month,
            "days_left": days_left,
            "is_behind": is_behind,
        }
