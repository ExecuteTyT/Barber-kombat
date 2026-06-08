"""Admin KPI: combines guest-survey admin scores with confirmation rate into a
per-branch admin score, and ranks branches for owner control + admin motivation.

The guest survey asks about "the administrator" (not a specific person), so the
KPI is attributed to the branch's admin(s).
"""

import uuid
from datetime import date

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.survey_response import SurveyResponse
from app.models.visit import Visit

# Composite weights (owner-chosen): guest-perceived admin quality vs. the
# objective confirmation rate of upcoming bookings.
_SURVEY_WEIGHT = 0.6
_CONFIRMATION_WEIGHT = 0.4


def _next_month(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


class AdminKpiService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_branch_kpi(self, branch_id: uuid.UUID, month_start: date) -> dict:
        """Admin KPI for one branch for the month containing ``month_start``."""
        month_start = month_start.replace(day=1)
        month_end = _next_month(month_start)

        survey = await self._survey_aggregates(branch_id, month_start, month_end)
        confirmation_rate = await self._confirmation_rate(branch_id)
        composite = self._composite(survey["admin_avg"], confirmation_rate)

        return {
            "branch_id": str(branch_id),
            "month": f"{month_start.year}-{month_start.month:02d}",
            "survey_count": survey["count"],
            "admin_avg": survey["admin_avg"],
            "master_avg": survey["master_avg"],
            "stars_avg": survey["stars_avg"],
            "nps": survey["nps"],
            "negatives": survey["negatives"],
            "confirmation_rate": confirmation_rate,
            "composite_score": composite,
        }

    async def get_network_kpi(self, organization_id: uuid.UUID, month_start: date) -> dict:
        """Per-branch admin KPI for the whole org, ranked by composite score."""
        result = await self.db.execute(
            select(Branch)
            .where(Branch.organization_id == organization_id, Branch.is_active.is_(True))
            .order_by(Branch.name)
        )
        branches = result.scalars().all()

        items = []
        for branch in branches:
            kpi = await self.get_branch_kpi(branch.id, month_start)
            kpi["branch_name"] = branch.name
            items.append(kpi)

        # Rank by composite (None last). Higher composite = better rank.
        items.sort(key=lambda k: (k["composite_score"] is None, -(k["composite_score"] or 0)))
        for idx, item in enumerate(items, start=1):
            item["rank"] = idx

        month_start = month_start.replace(day=1)
        return {
            "month": f"{month_start.year}-{month_start.month:02d}",
            "branches": items,
        }

    async def _survey_aggregates(
        self, branch_id: uuid.UUID, month_start: date, month_end: date
    ) -> dict:
        stmt = select(
            sa_func.count(SurveyResponse.id),
            sa_func.avg(SurveyResponse.admin_score),
            sa_func.avg(SurveyResponse.master_score),
            sa_func.avg(SurveyResponse.stars),
            sa_func.count().filter(SurveyResponse.recommend.is_(True)),
            sa_func.count().filter(SurveyResponse.is_negative.is_(True)),
        ).where(
            SurveyResponse.branch_id == branch_id,
            SurveyResponse.created_at >= month_start,
            SurveyResponse.created_at < month_end,
        )
        row = (await self.db.execute(stmt)).first()
        count = row[0] or 0
        return {
            "count": count,
            "admin_avg": round(row[1]) if row[1] is not None else None,
            "master_avg": round(row[2]) if row[2] is not None else None,
            "stars_avg": round(float(row[3]), 1) if row[3] is not None else None,
            "nps": round((row[4] or 0) / count * 100) if count else None,
            "negatives": row[5] or 0,
        }

    async def _confirmation_rate(self, branch_id: uuid.UUID) -> int:
        """Snapshot: % of upcoming scheduled visits that YClients marks confirmed."""
        today = date.today()
        stmt = select(
            sa_func.count(),
            sa_func.count().filter(Visit.confirmed.is_(True)),
        ).where(
            Visit.branch_id == branch_id,
            Visit.date >= today,
            Visit.status == "scheduled",
        )
        total, confirmed = (await self.db.execute(stmt)).first()
        return round((confirmed or 0) / total * 100) if total else 100

    @staticmethod
    def _composite(admin_avg: int | None, confirmation_rate: int) -> int | None:
        if admin_avg is None:
            return confirmation_rate
        return round(_SURVEY_WEIGHT * admin_avg + _CONFIRMATION_WEIGHT * confirmation_rate)
