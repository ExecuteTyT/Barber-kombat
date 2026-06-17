"""Regression tests for the calculation audit fixes.

Covers: avg-check rounding, KPI composite/month-awareness, _sum_products status
filter, prize-fund month bound, and review-score date cast.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin import AdminService
from app.services.admin_kpi import AdminKpiService
from app.services.rating import RatingEngine
from app.services.reports import ReportService, _avg_check

BRANCH = uuid.uuid4()
ORG = uuid.uuid4()


def _sql(stmt) -> str:
    return str(stmt).lower()


def _result(value):
    res = MagicMock()
    res.scalar_one.return_value = value
    return res


class TestAvgCheck:
    def test_rounds_not_floors(self):
        assert _avg_check(2000, 3) == 667  # round(666.67); floor would give 666
        assert _avg_check(1000, 4) == 250

    def test_zero_visits_guarded(self):
        assert _avg_check(5000, 0) == 0


class TestComposite:
    def test_confirmation_none_uses_admin(self):
        assert AdminKpiService._composite(70, None) == 70

    def test_admin_none_uses_confirmation(self):
        assert AdminKpiService._composite(None, 80) == 80

    def test_both_none(self):
        assert AdminKpiService._composite(None, None) is None

    def test_blend(self):
        assert AdminKpiService._composite(80, 90) == 84  # 0.6*80 + 0.4*90


class TestBranchKpiMonthAware:
    @pytest.mark.asyncio
    async def test_past_month_excludes_confirmation(self):
        svc = AdminKpiService(db=AsyncMock())
        svc._survey_aggregates = AsyncMock(
            return_value={
                "count": 3,
                "admin_avg": 70,
                "master_avg": 80,
                "stars_avg": 4.0,
                "nps": 66,
                "negatives": 0,
            }
        )
        svc._confirmation_rate = AsyncMock(return_value=100)

        past_month = (date.today().replace(day=1) - timedelta(days=40)).replace(day=1)
        kpi = await svc.get_branch_kpi(BRANCH, past_month)

        assert kpi["confirmation_rate"] is None
        assert kpi["composite_score"] == 70  # survey-only, no today's confirmation
        svc._confirmation_rate.assert_not_called()


class TestSumProductsFilter:
    @pytest.mark.asyncio
    async def test_only_counts_completed(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_result(0))
        await AdminService(db=db)._sum_products(BRANCH, date(2026, 6, 1))
        assert "status" in _sql(db.execute.call_args.args[0])


class TestPrizeFundBound:
    @pytest.mark.asyncio
    async def test_has_upper_date_bound(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_result(0))
        svc = RatingEngine(db=db, redis=MagicMock())
        svc._load_rating_config = AsyncMock(
            return_value=MagicMock(prize_gold_pct=0.5, prize_silver_pct=0.3, prize_bronze_pct=0.1)
        )
        await svc.get_prize_fund(BRANCH, ORG)
        rev_sql = next(
            _sql(c.args[0])
            for c in db.execute.call_args_list
            if "visits" in _sql(c.args[0]) and "revenue" in _sql(c.args[0])
        )
        # Both lower (>=) and upper (<) date bounds present.
        assert rev_sql.count("visits.date") >= 2


class TestAvgReviewScoreCast:
    @pytest.mark.asyncio
    async def test_casts_created_at_to_date(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_result(None))
        await ReportService(db=db)._avg_review_score(BRANCH, date(2026, 6, 1), date(2026, 6, 30))
        assert "cast" in _sql(db.execute.call_args.args[0])
