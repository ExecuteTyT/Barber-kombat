"""Tests for PVR API endpoints (rating-based)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import UserRole
from app.redis import get_redis


ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()


def make_user(
    role: str = "barber",
    user_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = BRANCH_ID,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.organization_id = ORG_ID
    user.branch_id = branch_id
    user.role = UserRole(role)
    user.name = "Test"
    user.is_active = True
    return user


def make_branch() -> MagicMock:
    b = MagicMock()
    b.id = BRANCH_ID
    b.organization_id = ORG_ID
    b.name = "Central"
    b.is_active = True
    return b


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# --- /pvr/thresholds ---


class TestGetThresholds:
    @pytest.mark.asyncio
    async def test_returns_defaults_without_config(self):
        user = make_user(role="barber")
        mock_db = AsyncMock()
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=config_result)
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/pvr/thresholds")

        assert response.status_code == 200
        data = response.json()
        assert "thresholds" in data
        assert data["min_visits_per_month"] == 0
        for t in data["thresholds"]:
            assert "score" in t
            assert "bonus" in t
            assert 0 <= t["score"] <= 100


# --- /pvr/preview ---


class TestPreviewPVR:
    @pytest.mark.asyncio
    async def test_owner_can_preview(self):
        user = make_user(role="owner", branch_id=None)
        branch = make_branch()

        mock_db = AsyncMock()
        # _validate_branch
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)
        mock_redis = AsyncMock()

        barber_preview = [
            {
                "barber_id": str(BARBER_ID_1),
                "name": "Pavel",
                "monthly_rating_score": 82,
                "working_days": 22,
                "current_threshold": 75,
                "bonus_amount": 200_000_000,
                "revenue": 35_000_000,
            },
        ]

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.pvr.PVRService.preview",
            new=AsyncMock(return_value=barber_preview),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/pvr/preview",
                    json={
                        "branch_id": str(BRANCH_ID),
                        "thresholds": [
                            {"score": 60, "bonus": 100_000_000},
                            {"score": 75, "bonus": 200_000_000},
                        ],
                        "min_visits_per_month": 20,
                    },
                )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_bonus_fund"] == 200_000_000
        assert len(data["barbers"]) == 1
        assert data["barbers"][0]["monthly_rating_score"] == 82

    @pytest.mark.asyncio
    async def test_barber_forbidden(self):
        user = make_user(role="barber")
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/pvr/preview",
                json={
                    "branch_id": str(BRANCH_ID),
                    "thresholds": [{"score": 60, "bonus": 100_000_000}],
                    "min_visits_per_month": 0,
                },
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_branch_not_found_404(self):
        user = make_user(role="owner", branch_id=None)
        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/pvr/preview",
                json={
                    "branch_id": str(uuid.uuid4()),
                    "thresholds": [{"score": 60, "bonus": 100_000_000}],
                    "min_visits_per_month": 0,
                },
            )

        assert response.status_code == 404


# --- /pvr/barber/{id} authorization ---


class TestGetBarberPVRAuth:
    @pytest.mark.asyncio
    async def test_barber_cannot_view_other_barber(self):
        me = make_user(role="barber", user_id=BARBER_ID_1)
        other = uuid.uuid4()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: me
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/pvr/barber/{other}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/pvr/barber/{BARBER_ID_1}")

        assert response.status_code in (401, 403)
