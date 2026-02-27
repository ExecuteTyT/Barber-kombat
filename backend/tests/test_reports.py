"""Tests for the ReportService (report generation logic)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.services.reports import ReportService, _month_label, _pct_change, _prev_month

# --- Test constants ---

ORG_ID = uuid.uuid4()
BRANCH_ID_1 = uuid.uuid4()
BRANCH_ID_2 = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()
BARBER_ID_2 = uuid.uuid4()


# --- Helpers ---


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID_1,
    org_id: uuid.UUID = ORG_ID,
    name: str = "8 \u043c\u0430\u0440\u0442\u0430",
) -> MagicMock:
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = name
    branch.is_active = True
    return branch


def make_plan(
    branch_id: uuid.UUID = BRANCH_ID_1,
    target: int = 240_000_000,
) -> MagicMock:
    plan = MagicMock()
    plan.branch_id = branch_id
    plan.target_amount = target
    return plan


def make_daily_rating(
    barber_id: uuid.UUID,
    name: str = "Pavel",
    rank: int = 1,
    total_score: float = 95.0,
    revenue: int = 1_350_000,
) -> MagicMock:
    dr = MagicMock()
    dr.barber_id = barber_id
    dr.rank = rank
    dr.total_score = total_score
    dr.revenue = revenue
    dr.revenue_score = 100.0
    dr.cs_value = 1.45
    dr.cs_score = 90.0
    dr.products_count = 2
    dr.products_score = 80.0
    dr.extras_count = 3
    dr.extras_score = 100.0
    dr.reviews_avg = 4.5
    dr.reviews_score = 85.0
    return dr


def make_report(
    report_type: str = "daily_revenue",
    report_date: date = date(2026, 2, 22),
    data: dict | None = None,
) -> MagicMock:
    report = MagicMock()
    report.id = uuid.uuid4()
    report.type = report_type
    report.date = report_date
    report.data = data or {"date": "2026-02-22", "branches": [], "network_total_today": 0, "network_total_mtd": 0}
    report.delivered_telegram = False
    return report


# --- Tests: helper functions ---


class TestPrevMonth:
    def test_february_to_january(self):
        assert _prev_month(date(2026, 2, 1)) == date(2026, 1, 1)

    def test_january_to_december(self):
        assert _prev_month(date(2026, 1, 1)) == date(2025, 12, 1)

    def test_march_to_february(self):
        assert _prev_month(date(2026, 3, 1)) == date(2026, 2, 1)

    def test_july_to_june(self):
        assert _prev_month(date(2026, 7, 1)) == date(2026, 6, 1)


class TestMonthLabel:
    def test_february_2026(self):
        assert _month_label(date(2026, 2, 1)) == "\u0424\u0435\u0432\u0440\u0430\u043b\u044c 2026"

    def test_october_2024(self):
        assert _month_label(date(2024, 10, 1)) == "\u041e\u043a\u0442\u044f\u0431\u0440\u044c 2024"

    def test_december_2025(self):
        assert _month_label(date(2025, 12, 1)) == "\u0414\u0435\u043a\u0430\u0431\u0440\u044c 2025"


class TestPctChange:
    def test_positive_change(self):
        assert _pct_change(114, 100) == "+14.0%"

    def test_negative_change(self):
        assert _pct_change(98, 100) == "-2.0%"

    def test_no_change(self):
        assert _pct_change(100, 100) == "+0.0%"

    def test_zero_previous(self):
        assert _pct_change(500, 0) == "+100.0%"

    def test_zero_both(self):
        assert _pct_change(0, 0) == "0.0%"

    def test_large_increase(self):
        assert _pct_change(200, 100) == "+100.0%"


# --- Tests: generate_daily_revenue ---


class TestGenerateDailyRevenue:
    @pytest.mark.asyncio
    async def test_generates_revenue_report(self):
        """Produces a report with per-branch revenue and network totals."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branch = make_branch(name="8 \u043c\u0430\u0440\u0442\u0430")

        # _get_active_branches
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [branch]

        # _sum_revenue (today), _sum_revenue (mtd)
        rev_today = MagicMock()
        rev_today.scalar_one.return_value = 8_500_000
        rev_mtd = MagicMock()
        rev_mtd.scalar_one.return_value = 185_000_000

        # _get_plan
        plan = make_plan(target=240_000_000)
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan

        # _count_barbers_in_shift
        shift_result = MagicMock()
        shift_result.scalar_one.return_value = 3

        # _count_barbers_total
        total_result = MagicMock()
        total_result.scalar_one.return_value = 4

        # _save_report (upsert execute + commit)
        save_result = MagicMock()

        mock_db.execute = AsyncMock(
            side_effect=[
                branches_result,
                rev_today, rev_mtd,
                plan_result,
                shift_result, total_result,
                save_result,
            ]
        )
        mock_db.commit = AsyncMock()

        data = await service.generate_daily_revenue(ORG_ID, date(2026, 2, 22))

        assert data["date"] == "2026-02-22"
        assert len(data["branches"]) == 1
        b = data["branches"][0]
        assert b["revenue_today"] == 8_500_000
        assert b["revenue_mtd"] == 185_000_000
        assert b["plan_target"] == 240_000_000
        assert b["plan_percentage"] == 77.1
        assert b["barbers_in_shift"] == 3
        assert b["barbers_total"] == 4
        assert data["network_total_today"] == 8_500_000
        assert data["network_total_mtd"] == 185_000_000

    @pytest.mark.asyncio
    async def test_no_plan_shows_zero(self):
        """When no plan exists, plan fields are 0."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branch = make_branch()

        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [branch]

        rev_today = MagicMock()
        rev_today.scalar_one.return_value = 5_000_000
        rev_mtd = MagicMock()
        rev_mtd.scalar_one.return_value = 50_000_000

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None

        shift_result = MagicMock()
        shift_result.scalar_one.return_value = 2
        total_result = MagicMock()
        total_result.scalar_one.return_value = 3

        save_result = MagicMock()

        mock_db.execute = AsyncMock(
            side_effect=[
                branches_result,
                rev_today, rev_mtd,
                plan_result,
                shift_result, total_result,
                save_result,
            ]
        )
        mock_db.commit = AsyncMock()

        data = await service.generate_daily_revenue(ORG_ID, date(2026, 2, 22))

        b = data["branches"][0]
        assert b["plan_target"] == 0
        assert b["plan_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_no_branches_empty_report(self):
        """No active branches produces empty report."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = []

        save_result = MagicMock()

        mock_db.execute = AsyncMock(side_effect=[branches_result, save_result])
        mock_db.commit = AsyncMock()

        data = await service.generate_daily_revenue(ORG_ID, date(2026, 2, 22))

        assert data["branches"] == []
        assert data["network_total_today"] == 0
        assert data["network_total_mtd"] == 0


# --- Tests: generate_day_to_day ---


class TestGenerateDayToDay:
    @pytest.mark.asyncio
    async def test_generates_comparison(self):
        """Produces 3-month comparison with cumulative data."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branch = make_branch()

        # _get_active_branches
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [branch]

        # For each of 3 months x day_num days of _sum_revenue calls
        # On Feb 5 (day 5), that's 5 days x 3 months = 15 calls
        # Plus branches query, plus save
        target = date(2026, 2, 5)
        day_revenues = []
        # Current month: 5 days
        for _ in range(5):
            r = MagicMock()
            r.scalar_one.return_value = 10_000_000
            day_revenues.append(r)
        # Prev month: 5 days
        for _ in range(5):
            r = MagicMock()
            r.scalar_one.return_value = 9_000_000
            day_revenues.append(r)
        # Prev prev month: 5 days
        for _ in range(5):
            r = MagicMock()
            r.scalar_one.return_value = 11_000_000
            day_revenues.append(r)

        save_result = MagicMock()

        mock_db.execute = AsyncMock(
            side_effect=[branches_result, *day_revenues, save_result]
        )
        mock_db.commit = AsyncMock()

        data = await service.generate_day_to_day(ORG_ID, target, branch_id=None)

        assert data["period_end"] == "2026-02-05"
        assert data["branch_id"] is None
        assert len(data["current_month"]["daily_cumulative"]) == 5
        assert data["current_month"]["daily_cumulative"][4]["amount"] == 50_000_000
        assert data["prev_month"]["daily_cumulative"][4]["amount"] == 45_000_000
        assert data["prev_prev_month"]["daily_cumulative"][4]["amount"] == 55_000_000
        # 50M vs 45M = +11.1%
        assert data["comparison"]["vs_prev"] == "+11.1%"
        # 50M vs 55M = -9.1%
        assert data["comparison"]["vs_prev_prev"] == "-9.1%"


# --- Tests: generate_clients_report ---


class TestGenerateClientsReport:
    @pytest.mark.asyncio
    async def test_generates_client_stats(self):
        """Produces new vs returning client counts."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branch = make_branch()

        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [branch]

        # _count_new_clients (today)
        new_today = MagicMock()
        new_today.scalar_one.return_value = 8
        # _count_unique_clients (today)
        total_today = MagicMock()
        total_today.scalar_one.return_value = 33
        # _count_new_clients (mtd)
        new_mtd = MagicMock()
        new_mtd.scalar_one.return_value = 105
        # _count_unique_clients (mtd)
        total_mtd = MagicMock()
        total_mtd.scalar_one.return_value = 811

        save_result = MagicMock()

        mock_db.execute = AsyncMock(
            side_effect=[
                branches_result,
                new_today, total_today,
                new_mtd, total_mtd,
                save_result,
            ]
        )
        mock_db.commit = AsyncMock()

        data = await service.generate_clients_report(ORG_ID, date(2026, 2, 22))

        assert data["date"] == "2026-02-22"
        b = data["branches"][0]
        assert b["new_clients_today"] == 8
        assert b["returning_clients_today"] == 25  # 33 - 8
        assert b["total_today"] == 33
        assert b["new_clients_mtd"] == 105
        assert b["returning_clients_mtd"] == 706  # 811 - 105
        assert b["total_mtd"] == 811
        assert data["network_new_mtd"] == 105
        assert data["network_returning_mtd"] == 706
        assert data["network_total_mtd"] == 811


# --- Tests: generate_kombat_daily ---


class TestGenerateKombatDaily:
    @pytest.mark.asyncio
    async def test_generates_daily_standings(self):
        """Produces Kombat standings from DailyRating."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branch = make_branch()

        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [branch]

        dr1 = make_daily_rating(BARBER_ID_1, name="Pavel", rank=1, total_score=95.0)
        dr2 = make_daily_rating(BARBER_ID_2, name="Leo", rank=2, total_score=82.0)

        ratings_result = MagicMock()
        ratings_result.all.return_value = [(dr1, "Pavel"), (dr2, "Leo")]

        save_result = MagicMock()

        mock_db.execute = AsyncMock(
            side_effect=[branches_result, ratings_result, save_result]
        )
        mock_db.commit = AsyncMock()

        data = await service.generate_kombat_daily(ORG_ID, date(2026, 2, 22))

        assert data["date"] == "2026-02-22"
        assert len(data["branches"]) == 1
        standings = data["branches"][0]["standings"]
        assert len(standings) == 2
        assert standings[0]["name"] == "Pavel"
        assert standings[0]["rank"] == 1
        assert standings[0]["total_score"] == 95.0
        assert standings[1]["name"] == "Leo"
        assert standings[1]["rank"] == 2


# --- Tests: generate_kombat_monthly ---


class TestGenerateKombatMonthly:
    @pytest.mark.asyncio
    async def test_generates_monthly_summary(self):
        """Produces monthly Kombat summary with aggregated scores."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        branch = make_branch()

        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [branch]

        # Aggregated query result
        row1 = MagicMock()
        row1.barber_id = BARBER_ID_1
        row1.name = "Pavel"
        row1.days_worked = 20
        row1.total_revenue = 27_000_000
        row1.avg_score = 88.5
        row1.wins = 12

        row2 = MagicMock()
        row2.barber_id = BARBER_ID_2
        row2.name = "Leo"
        row2.days_worked = 18
        row2.total_revenue = 24_000_000
        row2.avg_score = 79.3
        row2.wins = 5

        monthly_result = MagicMock()
        monthly_result.all.return_value = [row1, row2]

        save_result = MagicMock()

        mock_db.execute = AsyncMock(
            side_effect=[branches_result, monthly_result, save_result]
        )
        mock_db.commit = AsyncMock()

        data = await service.generate_kombat_monthly(ORG_ID, date(2026, 2, 1))

        assert data["month"] == "2026-02-01"
        standings = data["branches"][0]["standings"]
        assert len(standings) == 2
        assert standings[0]["name"] == "Pavel"
        assert standings[0]["rank"] == 1
        assert standings[0]["days_worked"] == 20
        assert standings[0]["avg_score"] == 88.5
        assert standings[0]["wins"] == 12
        assert standings[1]["name"] == "Leo"
        assert standings[1]["rank"] == 2


# --- Tests: get_report and list_reports ---


class TestReportRetrieval:
    @pytest.mark.asyncio
    async def test_get_report_found(self):
        """Returns a report when it exists."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        report = make_report()
        result = MagicMock()
        result.scalar_one_or_none.return_value = report
        mock_db.execute = AsyncMock(return_value=result)

        found = await service.get_report(ORG_ID, "daily_revenue", date(2026, 2, 22))
        assert found is not None
        assert found.type == "daily_revenue"

    @pytest.mark.asyncio
    async def test_get_report_not_found(self):
        """Returns None when no report exists."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        found = await service.get_report(ORG_ID, "daily_revenue", date(2026, 2, 22))
        assert found is None

    @pytest.mark.asyncio
    async def test_list_reports(self):
        """Returns a list of reports in date range."""
        mock_db = AsyncMock()
        service = ReportService(db=mock_db)

        r1 = make_report(report_date=date(2026, 2, 20))
        r2 = make_report(report_date=date(2026, 2, 21))

        result = MagicMock()
        result.scalars.return_value.all.return_value = [r2, r1]
        mock_db.execute = AsyncMock(return_value=result)

        reports = await service.list_reports(
            ORG_ID, "daily_revenue", date(2026, 2, 1), date(2026, 2, 28)
        )
        assert len(reports) == 2


# --- Tests: Celery beat schedule ---


class TestBeatSchedule:
    def test_daily_reports_scheduled(self):
        from app.tasks.celery_app import celery_app

        assert "report-daily-evening" in celery_app.conf.beat_schedule
        entry = celery_app.conf.beat_schedule["report-daily-evening"]
        assert entry["task"] == "generate_daily_reports"

    def test_day_to_day_scheduled(self):
        from app.tasks.celery_app import celery_app

        assert "report-day-to-day" in celery_app.conf.beat_schedule
        entry = celery_app.conf.beat_schedule["report-day-to-day"]
        assert entry["task"] == "generate_day_to_day"

    def test_monthly_reports_scheduled(self):
        from app.tasks.celery_app import celery_app

        assert "report-monthly" in celery_app.conf.beat_schedule
        entry = celery_app.conf.beat_schedule["report-monthly"]
        assert entry["task"] == "generate_monthly_reports"


# --- Tests: Celery task wrappers ---


class TestReportTasks:
    def test_generate_daily_reports_registered(self):
        from app.tasks.report_tasks import generate_daily_reports
        assert generate_daily_reports.name == "generate_daily_reports"

    def test_generate_day_to_day_registered(self):
        from app.tasks.report_tasks import generate_day_to_day
        assert generate_day_to_day.name == "generate_day_to_day"

    def test_generate_monthly_reports_registered(self):
        from app.tasks.report_tasks import generate_monthly_reports
        assert generate_monthly_reports.name == "generate_monthly_reports"
