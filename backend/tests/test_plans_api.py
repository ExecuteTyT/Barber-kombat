"""Tests for Plans API endpoints."""

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

# --- Test constants ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BRANCH_ID_2 = uuid.uuid4()
PLAN_ID = uuid.uuid4()


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


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
    name: str = "8 марта",
) -> MagicMock:
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = name
    branch.is_active = True
    return branch


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Clean up dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# --- Tests: GET /plans/{branch_id} ---


class TestGetBranchPlan:
    @pytest.mark.asyncio
    async def test_chef_can_view_plan(self):
        """Chef can view the plan for their branch."""
        user = make_user(role="chef")
        branch = make_branch()

        plan_data = {
            "id": PLAN_ID,
            "branch_id": BRANCH_ID,
            "branch_name": "8 марта",
            "month": "2026-02",
            "target_amount": 240_000_000,
            "current_amount": 185_000_000,
            "percentage": 77.1,
            "forecast_amount": 235_000_000,
            "required_daily": 3_670_000,
            "days_passed": 15,
            "days_in_month": 28,
            "days_left": 13,
            "is_behind": False,
        }

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # _validate_branch
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.get_plan_with_details",
            new_callable=AsyncMock,
            return_value=plan_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/plans/{BRANCH_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["branch_id"] == str(BRANCH_ID)
        assert data["branch_name"] == "8 марта"
        assert data["target_amount"] == 240_000_000
        assert data["current_amount"] == 185_000_000
        assert data["percentage"] == 77.1
        assert data["forecast_amount"] == 235_000_000
        assert data["required_daily"] == 3_670_000
        assert data["is_behind"] is False

    @pytest.mark.asyncio
    async def test_owner_can_view_plan(self):
        """Owner can view plans."""
        user = make_user(role="owner")
        branch = make_branch()

        plan_data = {
            "id": PLAN_ID,
            "branch_id": BRANCH_ID,
            "branch_name": "8 марта",
            "month": "2026-02",
            "target_amount": 200_000_000,
            "current_amount": 100_000_000,
            "percentage": 50.0,
            "forecast_amount": 200_000_000,
            "required_daily": None,
            "days_passed": 14,
            "days_in_month": 28,
            "days_left": 14,
            "is_behind": False,
        }

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.get_plan_with_details",
            new_callable=AsyncMock,
            return_value=plan_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/plans/{BRANCH_ID}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_barber_cannot_view_plan(self):
        """Barbers cannot view plans (requires chef/owner/admin role)."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/plans/{BRANCH_ID}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_plan_not_found_404(self):
        """Returns 404 when no plan exists for the branch/month."""
        user = make_user(role="chef")
        branch = make_branch()

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.get_plan_with_details",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/plans/{BRANCH_ID}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_branch_not_found_404(self):
        """Returns 404 when branch doesn't exist."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        fake_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/plans/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401/403 without authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/plans/{BRANCH_ID}")

        assert response.status_code in (401, 403)


# --- Tests: PUT /plans/{branch_id} ---


class TestUpsertBranchPlan:
    @pytest.mark.asyncio
    async def test_owner_can_create_plan(self):
        """Owner can create/update a plan."""
        user = make_user(role="owner")
        branch = make_branch()

        plan_data = {
            "id": PLAN_ID,
            "branch_id": BRANCH_ID,
            "branch_name": "8 марта",
            "month": "2026-02",
            "target_amount": 240_000_000,
            "current_amount": 0,
            "percentage": 0.0,
            "forecast_amount": None,
            "required_daily": None,
            "days_passed": 0,
            "days_in_month": 28,
            "days_left": 28,
            "is_behind": False,
        }

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.upsert_plan", new_callable=AsyncMock
        ) as mock_upsert, patch(
            "app.api.plans.PlanService.get_plan_with_details",
            new_callable=AsyncMock,
            return_value=plan_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    f"/api/v1/plans/{BRANCH_ID}",
                    json={"month": "2026-02-01", "target_amount": 240_000_000},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["target_amount"] == 240_000_000
        mock_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_chef_cannot_create_plan(self):
        """Chef cannot create/update plans (owner/admin only)."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.put(
                f"/api/v1/plans/{BRANCH_ID}",
                json={"month": "2026-02-01", "target_amount": 240_000_000},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_barber_cannot_create_plan(self):
        """Barber cannot create plans."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.put(
                f"/api/v1/plans/{BRANCH_ID}",
                json={"month": "2026-02-01", "target_amount": 240_000_000},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_target_amount(self):
        """Returns 422 for invalid target_amount (must be > 0)."""
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.put(
                f"/api/v1/plans/{BRANCH_ID}",
                json={"month": "2026-02-01", "target_amount": 0},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_can_create_plan(self):
        """Admin can create/update plans."""
        user = make_user(role="admin")
        branch = make_branch()

        plan_data = {
            "id": PLAN_ID,
            "branch_id": BRANCH_ID,
            "branch_name": "8 марта",
            "month": "2026-03",
            "target_amount": 300_000_000,
            "current_amount": 0,
            "percentage": 0.0,
            "forecast_amount": None,
            "required_daily": None,
            "days_passed": 0,
            "days_in_month": 31,
            "days_left": 31,
            "is_behind": False,
        }

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=branch_result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.upsert_plan", new_callable=AsyncMock
        ), patch(
            "app.api.plans.PlanService.get_plan_with_details",
            new_callable=AsyncMock,
            return_value=plan_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.put(
                    f"/api/v1/plans/{BRANCH_ID}",
                    json={"month": "2026-03-01", "target_amount": 300_000_000},
                )

        assert response.status_code == 200


# --- Tests: GET /plans/network/all ---


class TestGetNetworkPlans:
    @pytest.mark.asyncio
    async def test_owner_sees_all_branches(self):
        """Owner sees plans for all branches in the network."""
        user = make_user(role="owner")

        network_data = {
            "month": "2026-02",
            "plans": [
                {
                    "branch_id": BRANCH_ID,
                    "branch_name": "8 марта",
                    "target_amount": 240_000_000,
                    "current_amount": 185_000_000,
                    "percentage": 77.1,
                    "forecast_amount": 235_000_000,
                },
                {
                    "branch_id": BRANCH_ID_2,
                    "branch_name": "Ленина",
                    "target_amount": 200_000_000,
                    "current_amount": 160_000_000,
                    "percentage": 80.0,
                    "forecast_amount": 210_000_000,
                },
            ],
            "total_target": 440_000_000,
            "total_current": 345_000_000,
            "total_percentage": 78.4,
        }

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.get_network_plans",
            new_callable=AsyncMock,
            return_value=network_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/plans/network/all")

        assert response.status_code == 200
        data = response.json()
        assert data["month"] == "2026-02"
        assert len(data["plans"]) == 2
        assert data["total_target"] == 440_000_000
        assert data["total_current"] == 345_000_000
        assert data["total_percentage"] == 78.4

    @pytest.mark.asyncio
    async def test_chef_cannot_view_network(self):
        """Chef cannot view network-wide plans (owner/admin only)."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/plans/network/all")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_barber_cannot_view_network(self):
        """Barber cannot view network-wide plans."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/plans/network/all")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_network(self):
        """Returns empty plans list when no plans exist."""
        user = make_user(role="owner")

        network_data = {
            "month": "2026-02",
            "plans": [],
            "total_target": 0,
            "total_current": 0,
            "total_percentage": 0.0,
        }

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        with patch(
            "app.api.plans.PlanService.get_network_plans",
            new_callable=AsyncMock,
            return_value=network_data,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/plans/network/all")

        assert response.status_code == 200
        data = response.json()
        assert data["plans"] == []
        assert data["total_target"] == 0
