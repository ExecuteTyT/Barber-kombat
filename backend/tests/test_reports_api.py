"""Tests for Report API endpoints."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import UserRole

# --- Test constants ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()


# --- Helpers ---


def make_user(
    role: str = "owner",
    org_id: uuid.UUID = ORG_ID,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.organization_id = org_id
    user.branch_id = BRANCH_ID
    user.role = UserRole(role)
    user.name = "Test User"
    user.is_active = True
    return user


def make_report_obj(
    report_type: str = "daily_revenue",
    data: dict | None = None,
) -> MagicMock:
    """Create a mock Report object."""
    report = MagicMock()
    report.id = uuid.uuid4()
    report.type = report_type
    report.date = date(2026, 2, 22)
    report.branch_id = None
    report.data = data
    report.delivered_telegram = False
    return report


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Clean up dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# --- Tests: GET /reports/revenue ---


class TestGetRevenueReport:
    @pytest.mark.asyncio
    async def test_owner_gets_revenue_report(self):
        """Owner can view the daily revenue report."""
        user = make_user(role="owner")

        report_data = {
            "date": "2026-02-22",
            "branches": [
                {
                    "branch_id": str(BRANCH_ID),
                    "name": "Test Branch",
                    "revenue_today": 8_500_000,
                    "revenue_mtd": 185_000_000,
                    "plan_target": 240_000_000,
                    "plan_percentage": 77.1,
                    "barbers_in_shift": 3,
                    "barbers_total": 4,
                }
            ],
            "network_total_today": 8_500_000,
            "network_total_mtd": 185_000_000,
        }
        report = make_report_obj(data=report_data)

        mock_db = AsyncMock()

        # get_report -> found a pre-generated report
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = report
        mock_db.execute = AsyncMock(return_value=report_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/reports/revenue",
                params={"target_date": "2026-02-22"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-02-22"
        assert len(data["branches"]) == 1
        assert data["network_total_today"] == 8_500_000

    @pytest.mark.asyncio
    async def test_barber_forbidden(self):
        """Barbers cannot access revenue reports."""
        user = make_user(role="barber")

        mock_db = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reports/revenue")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401/403 without authentication."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reports/revenue")

        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_generates_on_the_fly_when_not_cached(self):
        """When no stored report exists, generates one on-the-fly."""
        user = make_user(role="owner")

        mock_db = AsyncMock()

        # get_report -> None (not found)
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = None

        # generate_daily_revenue needs: branches, revenue queries, plan, etc.
        # Simplest approach: mock at service level
        mock_db.execute = AsyncMock(return_value=report_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        generated_data = {
            "date": "2026-02-22",
            "branches": [],
            "network_total_today": 0,
            "network_total_mtd": 0,
        }

        with patch(
            "app.api.reports.ReportService.generate_daily_revenue",
            new_callable=AsyncMock,
            return_value=generated_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/reports/revenue",
                    params={"target_date": "2026-02-22"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["branches"] == []


# --- Tests: GET /reports/day-to-day ---


class TestGetDayToDayReport:
    @pytest.mark.asyncio
    async def test_returns_day_to_day_report(self):
        """Returns a stored day-to-day report."""
        user = make_user(role="owner")

        report_data = {
            "branch_id": None,
            "period_end": "2026-02-22",
            "current_month": {
                "name": "\u0424\u0435\u0432\u0440\u0430\u043b\u044c 2026",
                "daily_cumulative": [{"day": 1, "amount": 10_000_000}],
            },
            "prev_month": {
                "name": "\u042f\u043d\u0432\u0430\u0440\u044c 2026",
                "daily_cumulative": [{"day": 1, "amount": 9_000_000}],
            },
            "prev_prev_month": {
                "name": "\u0414\u0435\u043a\u0430\u0431\u0440\u044c 2025",
                "daily_cumulative": [{"day": 1, "amount": 11_000_000}],
            },
            "comparison": {
                "vs_prev": "+11.1%",
                "vs_prev_prev": "-9.1%",
            },
        }
        report = make_report_obj(report_type="day_to_day", data=report_data)

        mock_db = AsyncMock()
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = report
        mock_db.execute = AsyncMock(return_value=report_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/reports/day-to-day",
                params={"target_date": "2026-02-22"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["period_end"] == "2026-02-22"
        assert data["comparison"]["vs_prev"] == "+11.1%"

    @pytest.mark.asyncio
    async def test_chef_forbidden(self):
        """Chefs cannot access day-to-day reports."""
        user = make_user(role="chef")
        mock_db = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reports/day-to-day")

        assert response.status_code == 403


# --- Tests: GET /reports/clients ---


class TestGetClientsReport:
    @pytest.mark.asyncio
    async def test_returns_clients_report(self):
        """Returns a stored clients report."""
        user = make_user(role="manager")

        report_data = {
            "date": "2026-02-22",
            "branches": [
                {
                    "branch_id": str(BRANCH_ID),
                    "name": "Test Branch",
                    "new_clients_today": 8,
                    "returning_clients_today": 25,
                    "total_today": 33,
                    "new_clients_mtd": 105,
                    "returning_clients_mtd": 706,
                    "total_mtd": 811,
                }
            ],
            "network_new_mtd": 105,
            "network_returning_mtd": 706,
            "network_total_mtd": 811,
        }
        report = make_report_obj(report_type="clients", data=report_data)

        mock_db = AsyncMock()
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = report
        mock_db.execute = AsyncMock(return_value=report_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/reports/clients",
                params={"target_date": "2026-02-22"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["network_new_mtd"] == 105
        assert data["network_total_mtd"] == 811


# --- Tests: GET /reports/bingo ---


class TestGetBingoReport:
    @pytest.mark.asyncio
    async def test_chef_can_view_bingo(self):
        """Chef can access Kombat daily standings."""
        user = make_user(role="chef")

        report_data = {
            "date": "2026-02-22",
            "branches": [
                {
                    "branch_id": str(BRANCH_ID),
                    "name": "Test Branch",
                    "standings": [
                        {
                            "barber_id": str(uuid.uuid4()),
                            "name": "Pavel",
                            "rank": 1,
                            "total_score": 95.0,
                            "revenue": 1_350_000,
                            "revenue_score": 100.0,
                            "cs_value": 1.45,
                            "cs_score": 90.0,
                            "products_count": 2,
                            "products_score": 80.0,
                            "extras_count": 3,
                            "extras_score": 100.0,
                            "reviews_avg": 4.5,
                            "reviews_score": 85.0,
                        }
                    ],
                }
            ],
        }
        report = make_report_obj(report_type="kombat_daily", data=report_data)

        mock_db = AsyncMock()
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = report
        mock_db.execute = AsyncMock(return_value=report_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/reports/bingo",
                params={"target_date": "2026-02-22"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-02-22"
        assert len(data["branches"]) == 1
        assert data["branches"][0]["standings"][0]["name"] == "Pavel"

    @pytest.mark.asyncio
    async def test_barber_forbidden_for_bingo(self):
        """Barbers cannot access bingo endpoint."""
        user = make_user(role="barber")
        mock_db = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/reports/bingo")

        assert response.status_code == 403


# --- Tests: GET /reports/bingo/monthly ---


class TestGetBingoMonthlyReport:
    @pytest.mark.asyncio
    async def test_owner_gets_monthly_bingo(self):
        """Owner can view monthly Kombat summary."""
        user = make_user(role="owner")

        report_data = {
            "month": "2026-02-01",
            "branches": [
                {
                    "branch_id": str(BRANCH_ID),
                    "name": "Test Branch",
                    "standings": [
                        {
                            "barber_id": str(uuid.uuid4()),
                            "name": "Pavel",
                            "days_worked": 20,
                            "total_revenue": 27_000_000,
                            "avg_score": 88.5,
                            "wins": 12,
                            "rank": 1,
                        }
                    ],
                }
            ],
        }
        report = make_report_obj(report_type="kombat_monthly", data=report_data)

        mock_db = AsyncMock()
        report_result = MagicMock()
        report_result.scalar_one_or_none.return_value = report
        mock_db.execute = AsyncMock(return_value=report_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/reports/bingo/monthly",
                params={"month": "2026-02-01"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "2026-02-01"
        standings = data["branches"][0]["standings"]
        assert standings[0]["name"] == "Pavel"
        assert standings[0]["wins"] == 12
