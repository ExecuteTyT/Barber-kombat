"""Tests for Barber Kombat API endpoints."""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import UserRole
from app.redis import get_redis

# --- Test constants ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()
BARBER_ID_2 = uuid.uuid4()
BARBER_ID_3 = uuid.uuid4()


# --- Helpers ---


def make_user(
    role: str = "barber",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.organization_id = org_id
    user.branch_id = branch_id
    user.role = UserRole(role)
    user.name = "Test User"
    user.is_active = True
    return user


def make_daily_rating(
    barber_id: uuid.UUID,
    name: str = "Barber",
    rank: int = 1,
    total_score: float = 100.0,
    revenue: int = 1350000,
    target_date: date | None = None,
) -> MagicMock:
    """Create a mock DailyRating object."""
    dr = MagicMock()
    dr.barber_id = barber_id
    dr.rank = rank
    dr.total_score = total_score
    dr.revenue = revenue
    dr.revenue_score = 100.0
    dr.cs_value = 1.45
    dr.cs_score = 95.4
    dr.products_count = 2
    dr.products_score = 80.0
    dr.extras_count = 3
    dr.extras_score = 100.0
    dr.reviews_avg = 4.5
    dr.reviews_score = 90.0
    dr.date = target_date or date.today()
    return dr


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
    name: str = "Test Branch",
) -> MagicMock:
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = name
    branch.is_active = True
    return branch


def make_plan(
    target: int = 240000000,
    current: int = 185000000,
    percentage: float = 77.1,
    forecast: int | None = 235000000,
) -> MagicMock:
    """Create a mock Plan object."""
    plan = MagicMock()
    plan.target_amount = target
    plan.current_amount = current
    plan.percentage = percentage
    plan.forecast_amount = forecast
    return plan


def make_rating_config(
    org_id: uuid.UUID = ORG_ID,
    revenue_weight: int = 20,
    cs_weight: int = 20,
    products_weight: int = 25,
    extras_weight: int = 25,
    reviews_weight: int = 10,
) -> MagicMock:
    """Create a mock RatingConfig object."""
    config = MagicMock()
    config.organization_id = org_id
    config.revenue_weight = revenue_weight
    config.cs_weight = cs_weight
    config.products_weight = products_weight
    config.extras_weight = extras_weight
    config.reviews_weight = reviews_weight
    return config


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Clean up dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# --- Tests: GET /kombat/today/{branch_id} ---


class TestTodayRating:
    @pytest.mark.asyncio
    async def test_returns_cached_rating(self):
        """When Redis has cached data, return it directly."""
        user = make_user(role="barber")

        cached_data = {
            "type": "rating_update",
            "branch_id": str(BRANCH_ID),
            "date": str(date.today()),
            "ratings": [
                {
                    "barber_id": str(BARBER_ID_1),
                    "name": "Pavel",
                    "rank": 1,
                    "total_score": 100.0,
                    "revenue": 1350000,
                    "revenue_score": 100.0,
                    "cs_value": 1.45,
                    "cs_score": 95.4,
                    "products_count": 2,
                    "products_score": 80.0,
                    "extras_count": 3,
                    "extras_score": 100.0,
                    "reviews_avg": 4.5,
                    "reviews_score": 90.0,
                },
            ],
            "prize_fund": {"gold": 490000, "silver": 294000, "bronze": 98000},
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        branch = make_branch()

        # DB calls: _validate_branch, plan query, config query
        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, plan_result, config_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/today/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["branch_id"] == str(BRANCH_ID)
        assert data["branch_name"] == "Test Branch"
        assert len(data["ratings"]) == 1
        assert data["ratings"][0]["name"] == "Pavel"
        assert data["ratings"][0]["rank"] == 1
        assert data["prize_fund"]["gold"] == 490000
        assert data["plan"] is None
        assert data["weights"]["revenue"] == 20

    @pytest.mark.asyncio
    async def test_returns_db_rating_on_cache_miss(self):
        """When Redis cache misses, fall back to DB query."""
        user = make_user(role="chef")

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        branch = make_branch()
        dr = make_daily_rating(BARBER_ID_1, name="Pavel")

        # DB calls: _validate_branch, DailyRating query, prize_fund config,
        # prize_fund revenue, plan query, config query
        mock_db = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        # DailyRating + User.name join result
        dr_rows = MagicMock()
        dr_rows.all.return_value = [(dr, "Pavel")]

        # Prize fund: config query
        pf_config_result = MagicMock()
        pf_config_result.scalar_one_or_none.return_value = None

        # Prize fund: revenue query
        pf_revenue_result = MagicMock()
        pf_revenue_result.scalar_one.return_value = 9800000

        # Plan query
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None

        # Weights config query
        weights_result = MagicMock()
        weights_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[
                branch_result,
                dr_rows,
                pf_config_result,
                pf_revenue_result,
                plan_result,
                weights_result,
            ]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/today/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["ratings"]) == 1
        assert data["ratings"][0]["name"] == "Pavel"
        assert data["prize_fund"]["gold"] == 49000

    @pytest.mark.asyncio
    async def test_includes_plan_data(self):
        """When a Plan exists, response includes plan section."""
        user = make_user(role="owner")

        cached_data = {
            "ratings": [],
            "prize_fund": {"gold": 0, "silver": 0, "bronze": 0},
        }
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        branch = make_branch()
        plan = make_plan()

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, plan_result, config_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/today/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] is not None
        assert data["plan"]["target"] == 240000000
        assert data["plan"]["current"] == 185000000
        assert data["plan"]["percentage"] == 77.1

    @pytest.mark.asyncio
    async def test_branch_not_found_404(self):
        """Returns 404 for unknown branch."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        fake_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/today/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401 without a valid token."""
        # Don't override get_current_user — let it fail naturally
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/today/{BRANCH_ID}")

        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_includes_weights_from_config(self):
        """Weights come from RatingConfig when it exists."""
        user = make_user(role="barber")

        cached_data = {
            "ratings": [],
            "prize_fund": {"gold": 0, "silver": 0, "bronze": 0},
        }
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        branch = make_branch()
        config = make_rating_config(
            revenue_weight=30, cs_weight=30, products_weight=15,
            extras_weight=15, reviews_weight=10,
        )

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, plan_result, config_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/today/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["weights"]["revenue"] == 30
        assert data["weights"]["cs"] == 30
        assert data["weights"]["products"] == 15


# --- Tests: GET /kombat/standings/{branch_id} ---


class TestStandings:
    @pytest.mark.asyncio
    async def test_current_month(self):
        """Returns standings for current month by default."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        standings_result = MagicMock()
        row1 = MagicMock()
        row1.barber_id = BARBER_ID_1
        row1.name = "Pavel"
        row1.wins = 7
        row1.avg_score = 95.2
        row2 = MagicMock()
        row2.barber_id = BARBER_ID_2
        row2.name = "Lev"
        row2.wins = 4
        row2.avg_score = 88.1
        standings_result.all.return_value = [row1, row2]

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, standings_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/standings/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["branch_id"] == str(BRANCH_ID)
        assert len(data["standings"]) == 2
        assert data["standings"][0]["name"] == "Pavel"
        assert data["standings"][0]["wins"] == 7

    @pytest.mark.asyncio
    async def test_specific_month_param(self):
        """Accepts month=YYYY-MM query param."""
        user = make_user(role="owner")

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        standings_result = MagicMock()
        standings_result.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, standings_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/standings/{BRANCH_ID}?month=2024-10"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "2024-10"

    @pytest.mark.asyncio
    async def test_empty_standings(self):
        """Returns empty list when no ratings exist for the month."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        standings_result = MagicMock()
        standings_result.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, standings_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/standings/{BRANCH_ID}")

        assert response.status_code == 200
        assert response.json()["standings"] == []

    @pytest.mark.asyncio
    async def test_wrong_org_404(self):
        """Returns 404 when branch belongs to a different org."""
        other_org = uuid.uuid4()
        user = make_user(role="barber", org_id=other_org)

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/standings/{BRANCH_ID}")

        assert response.status_code == 404


# --- Tests: GET /kombat/history/{branch_id} ---


class TestHistory:
    @pytest.mark.asyncio
    async def test_returns_history_with_winners(self):
        """Returns daily history grouped by date with winners."""
        user = make_user(role="chef")

        today = date.today()
        dr1 = make_daily_rating(BARBER_ID_1, rank=1, target_date=today)
        dr2 = make_daily_rating(BARBER_ID_2, rank=2, total_score=85.0, target_date=today)

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        history_result = MagicMock()
        history_result.all.return_value = [
            (dr1, "Pavel"),
            (dr2, "Lev"),
        ]

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, history_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/history/{BRANCH_ID}"
                f"?date_from={today}&date_to={today}"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["days"]) == 1
        day = data["days"][0]
        assert day["winner"]["name"] == "Pavel"
        assert len(day["ratings"]) == 2

    @pytest.mark.asyncio
    async def test_owner_can_access(self):
        """Owner role can access history endpoint."""
        user = make_user(role="owner")

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = make_branch()

        history_result = MagicMock()
        history_result.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, history_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        today = date.today()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/history/{BRANCH_ID}"
                f"?date_from={today}&date_to={today}"
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_barber_forbidden_403(self):
        """Barber role cannot access history endpoint."""
        user = make_user(role="barber")

        app.dependency_overrides[get_current_user] = lambda: user

        today = date.today()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/history/{BRANCH_ID}"
                f"?date_from={today}&date_to={today}"
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_requires_date_params(self):
        """Returns 422 when date params are missing."""
        user = make_user(role="chef")

        app.dependency_overrides[get_current_user] = lambda: user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/kombat/history/{BRANCH_ID}")

        assert response.status_code == 422


# --- Tests: GET /kombat/barber/{barber_id}/stats ---


class TestBarberStats:
    @pytest.mark.asyncio
    async def test_returns_full_stats(self):
        """Returns complete barber stats for a month."""
        user = make_user(role="barber")

        barber = MagicMock()
        barber.id = BARBER_ID_1
        barber.name = "Pavel"
        barber.organization_id = ORG_ID

        today = date.today()
        dr1 = make_daily_rating(BARBER_ID_1, rank=1, total_score=100.0, target_date=today)
        dr2 = make_daily_rating(BARBER_ID_1, rank=2, total_score=85.0, target_date=today)

        mock_db = AsyncMock()

        # Barber validation
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        # DailyRating query
        dr_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [dr1, dr2]
        dr_result.scalars.return_value = scalars

        mock_db.execute = AsyncMock(
            side_effect=[barber_result, dr_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/barber/{BARBER_ID_1}/stats"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["barber_id"] == str(BARBER_ID_1)
        assert data["name"] == "Pavel"
        assert data["wins"] == 1
        assert data["avg_score"] == 92.5
        assert len(data["daily_scores"]) == 2

    @pytest.mark.asyncio
    async def test_barber_not_found_404(self):
        """Returns 404 when barber doesn't exist."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=barber_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        fake_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/barber/{fake_id}/stats"
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_org_barber_404(self):
        """Returns 404 when barber belongs to different org."""
        other_org = uuid.uuid4()
        user = make_user(role="barber", org_id=other_org)

        mock_db = AsyncMock()
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=barber_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/barber/{BARBER_ID_1}/stats"
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_specific_month(self):
        """Accepts month query parameter."""
        user = make_user(role="chef")

        barber = MagicMock()
        barber.id = BARBER_ID_1
        barber.name = "Pavel"
        barber.organization_id = ORG_ID

        mock_db = AsyncMock()
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        dr_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        dr_result.scalars.return_value = scalars

        mock_db.execute = AsyncMock(
            side_effect=[barber_result, dr_result]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/kombat/barber/{BARBER_ID_1}/stats?month=2024-10"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "2024-10"
        assert data["wins"] == 0
        assert data["daily_scores"] == []
