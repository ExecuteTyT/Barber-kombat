"""Tests for PVR API endpoints."""

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
) -> MagicMock:
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = "Test Branch"
    branch.is_active = True
    return branch


def make_barber(
    barber_id: uuid.UUID = BARBER_ID_1,
    name: str = "Pavel",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
) -> MagicMock:
    """Create a mock User (barber) object."""
    barber = MagicMock()
    barber.id = barber_id
    barber.name = name
    barber.organization_id = org_id
    barber.branch_id = branch_id
    barber.is_active = True
    barber.role = UserRole.BARBER
    return barber


def make_pvr_config(
    org_id: uuid.UUID = ORG_ID,
    thresholds: list[dict] | None = None,
    count_products: bool = False,
    count_certificates: bool = False,
) -> MagicMock:
    """Create a mock PVRConfig object."""
    config = MagicMock()
    config.organization_id = org_id
    config.thresholds = thresholds
    config.count_products = count_products
    config.count_certificates = count_certificates
    return config


def make_pvr_record(
    barber_id: uuid.UUID = BARBER_ID_1,
    cumulative_revenue: int = 0,
    current_threshold: int | None = None,
    bonus_amount: int = 0,
    thresholds_reached: list | None = None,
) -> MagicMock:
    """Create a mock PVRRecord object."""
    record = MagicMock()
    record.barber_id = barber_id
    record.month = date.today().replace(day=1)
    record.cumulative_revenue = cumulative_revenue
    record.current_threshold = current_threshold
    record.bonus_amount = bonus_amount
    record.thresholds_reached = thresholds_reached
    return record


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Clean up dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


# --- Tests: GET /pvr/{branch_id}/current ---


class TestGetBranchPVR:
    @pytest.mark.asyncio
    async def test_chef_can_view_branch_pvr(self):
        """Chef can view PVR for all barbers in their branch."""
        user = make_user(role="chef")
        branch = make_branch()

        # Two barbers with PVR records
        barber1 = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        barber2 = make_barber(barber_id=BARBER_ID_2, name="Leo")

        record1 = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=40_000_000,
            current_threshold=40_000_000,
            bonus_amount=2_000_000,
            thresholds_reached=[
                {"amount": 30_000_000, "reached_at": "2026-02-05"},
                {"amount": 35_000_000, "reached_at": "2026-02-09"},
                {"amount": 40_000_000, "reached_at": "2026-02-14"},
            ],
        )
        record2 = make_pvr_record(
            barber_id=BARBER_ID_2,
            cumulative_revenue=28_000_000,
            current_threshold=None,
            bonus_amount=0,
            thresholds_reached=None,
        )

        mock_db = AsyncMock()

        # _validate_branch
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        # get_branch_pvr -> select barbers
        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = [barber1, barber2]

        # _load_config
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # _get_record for barber1
        record1_result = MagicMock()
        record1_result.scalar_one_or_none.return_value = record1

        # _get_record for barber2
        record2_result = MagicMock()
        record2_result.scalar_one_or_none.return_value = record2

        mock_db.execute = AsyncMock(
            side_effect=[
                branch_result, barbers_result, config_result,
                record1_result, record2_result,
            ]
        )

        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/{BRANCH_ID}/current")

        assert response.status_code == 200
        data = response.json()
        assert data["branch_id"] == str(BRANCH_ID)
        assert len(data["barbers"]) == 2

        # Barber 1 has threshold
        b1 = next(b for b in data["barbers"] if b["barber_id"] == str(BARBER_ID_1))
        assert b1["name"] == "Pavel"
        assert b1["cumulative_revenue"] == 40_000_000
        assert b1["current_threshold"] == 40_000_000
        assert b1["bonus_amount"] == 2_000_000
        assert b1["next_threshold"] == 50_000_000

        # Barber 2 has no threshold
        b2 = next(b for b in data["barbers"] if b["barber_id"] == str(BARBER_ID_2))
        assert b2["name"] == "Leo"
        assert b2["current_threshold"] is None
        assert b2["bonus_amount"] == 0

    @pytest.mark.asyncio
    async def test_owner_can_view_branch_pvr(self):
        """Owner can also view branch PVR."""
        user = make_user(role="owner")
        branch = make_branch()

        mock_db = AsyncMock()
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        barbers_result = MagicMock()
        barbers_result.scalars.return_value.all.return_value = []

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[branch_result, barbers_result, config_result]
        )

        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/{BRANCH_ID}/current")

        assert response.status_code == 200
        data = response.json()
        assert data["barbers"] == []

    @pytest.mark.asyncio
    async def test_barber_cannot_view_branch_pvr(self):
        """Barbers don't have access to the branch-level PVR endpoint."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/{BRANCH_ID}/current")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_branch_not_found_404(self):
        """Returns 404 when branch doesn't exist or belongs to another org."""
        user = make_user(role="chef")

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
            response = await client.get(f"/api/v1/pvr/{fake_id}/current")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401/403 without authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/{BRANCH_ID}/current")

        assert response.status_code in (401, 403)


# --- Tests: GET /pvr/barber/{barber_id} ---


class TestGetBarberPVR:
    @pytest.mark.asyncio
    async def test_barber_sees_own_pvr(self):
        """A barber can view their own PVR data."""
        user = make_user(role="barber", user_id=BARBER_ID_1)
        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")

        record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=35_000_000,
            current_threshold=35_000_000,
            bonus_amount=1_500_000,
            thresholds_reached=[
                {"amount": 30_000_000, "reached_at": "2026-02-05"},
                {"amount": 35_000_000, "reached_at": "2026-02-12"},
            ],
        )

        mock_db = AsyncMock()

        # Validate barber belongs to org
        barber_check = MagicMock()
        barber_check.scalar_one_or_none.return_value = barber

        # PVR record
        record_result = MagicMock()
        record_result.scalar_one_or_none.return_value = record

        # Config
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # Barber info
        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        mock_db.execute = AsyncMock(
            side_effect=[barber_check, record_result, config_result, barber_result]
        )

        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/barber/{BARBER_ID_1}")

        assert response.status_code == 200
        data = response.json()
        assert data["barber_id"] == str(BARBER_ID_1)
        assert data["name"] == "Pavel"
        assert data["cumulative_revenue"] == 35_000_000
        assert data["current_threshold"] == 35_000_000
        assert data["bonus_amount"] == 1_500_000
        assert data["next_threshold"] == 40_000_000
        assert data["remaining_to_next"] == 5_000_000
        assert len(data["thresholds_reached"]) == 2

    @pytest.mark.asyncio
    async def test_barber_cannot_see_other_barber(self):
        """A barber cannot view another barber's PVR."""
        user = make_user(role="barber", user_id=BARBER_ID_1)

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/barber/{BARBER_ID_2}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_chef_can_see_any_barber(self):
        """Chef can view any barber's PVR in their org."""
        user = make_user(role="chef")
        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")

        record = make_pvr_record(
            barber_id=BARBER_ID_1,
            cumulative_revenue=50_000_000,
            current_threshold=50_000_000,
            bonus_amount=3_000_000,
        )

        mock_db = AsyncMock()

        barber_check = MagicMock()
        barber_check.scalar_one_or_none.return_value = barber

        record_result = MagicMock()
        record_result.scalar_one_or_none.return_value = record

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        barber_result = MagicMock()
        barber_result.scalar_one_or_none.return_value = barber

        mock_db.execute = AsyncMock(
            side_effect=[barber_check, record_result, config_result, barber_result]
        )

        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/barber/{BARBER_ID_1}")

        assert response.status_code == 200
        data = response.json()
        assert data["cumulative_revenue"] == 50_000_000

    @pytest.mark.asyncio
    async def test_barber_not_found_404(self):
        """Returns 404 when barber doesn't exist in user's org."""
        user = make_user(role="chef")

        mock_db = AsyncMock()
        barber_check = MagicMock()
        barber_check.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=barber_check)

        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        fake_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/pvr/barber/{fake_id}")

        assert response.status_code == 404


# --- Tests: GET /pvr/thresholds ---


class TestGetThresholds:
    @pytest.mark.asyncio
    async def test_returns_default_thresholds(self):
        """Returns default thresholds when no config exists."""
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        # PVRService.get_thresholds calls _load_config
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        # The thresholds endpoint also calls _load_config again for count flags
        config_result2 = MagicMock()
        config_result2.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(
            side_effect=[config_result, config_result2]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/pvr/thresholds")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 6
        assert data["thresholds"][0]["amount"] == 30_000_000
        assert data["thresholds"][-1]["amount"] == 80_000_000
        assert data["count_products"] is False
        assert data["count_certificates"] is False

    @pytest.mark.asyncio
    async def test_returns_custom_thresholds_with_flags(self):
        """Returns custom thresholds and config flags."""
        user = make_user(role="owner")

        custom_thresholds = [
            {"amount": 20_000_000, "bonus": 500_000},
            {"amount": 40_000_000, "bonus": 1_500_000},
        ]
        config = make_pvr_config(
            thresholds=custom_thresholds,
            count_products=True,
            count_certificates=False,
        )

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        config_result2 = MagicMock()
        config_result2.scalar_one_or_none.return_value = config

        mock_db.execute = AsyncMock(
            side_effect=[config_result, config_result2]
        )

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/pvr/thresholds")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 2
        assert data["thresholds"][0]["amount"] == 20_000_000
        assert data["thresholds"][1]["amount"] == 40_000_000
        assert data["count_products"] is True
        assert data["count_certificates"] is False

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        """Returns 401/403 without authentication."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/pvr/thresholds")

        assert response.status_code in (401, 403)
