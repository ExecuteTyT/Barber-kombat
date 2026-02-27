"""Tests for Config API endpoints."""

import uuid
from datetime import UTC, datetime
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
USER_ID = uuid.uuid4()
NOTIF_ID = uuid.uuid4()


# --- Helpers ---


def make_user(
    role: str = "owner",
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.organization_id = org_id
    user.branch_id = branch_id
    user.role = UserRole(role)
    user.name = "Test Owner"
    user.is_active = True
    return user


def make_rating_config() -> MagicMock:
    config = MagicMock()
    config.id = uuid.uuid4()
    config.organization_id = ORG_ID
    config.revenue_weight = 30
    config.cs_weight = 20
    config.products_weight = 20
    config.extras_weight = 20
    config.reviews_weight = 10
    config.prize_gold_pct = 0.5
    config.prize_silver_pct = 0.3
    config.prize_bronze_pct = 0.1
    config.extra_services = ["воск", "массаж"]
    return config


def make_pvr_config() -> MagicMock:
    config = MagicMock()
    config.id = uuid.uuid4()
    config.organization_id = ORG_ID
    config.thresholds = [
        {"amount": 30_000_000, "bonus": 1_000_000},
        {"amount": 50_000_000, "bonus": 3_000_000},
    ]
    config.count_products = True
    config.count_certificates = False
    return config


def make_branch_model() -> MagicMock:
    branch = MagicMock()
    branch.id = BRANCH_ID
    branch.organization_id = ORG_ID
    branch.name = "Main Branch"
    branch.address = "123 Main St"
    branch.yclients_company_id = None
    branch.telegram_group_id = None
    branch.is_active = True
    branch.created_at = datetime.now(UTC)
    branch.updated_at = datetime.now(UTC)
    return branch


def make_user_model(user_id: uuid.UUID = USER_ID) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.organization_id = ORG_ID
    user.branch_id = BRANCH_ID
    user.telegram_id = 123456789
    user.role = UserRole.BARBER
    user.name = "Pavel"
    user.grade = "senior"
    user.haircut_price = 200_000
    user.yclients_staff_id = None
    user.is_active = True
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    return user


def make_notif_model(notif_id: uuid.UUID = NOTIF_ID) -> MagicMock:
    notif = MagicMock()
    notif.id = notif_id
    notif.organization_id = ORG_ID
    notif.branch_id = None
    notif.notification_type = "daily_rating"
    notif.telegram_chat_id = -1001234567890
    notif.is_enabled = True
    notif.schedule_time = None
    notif.created_at = datetime.now(UTC)
    return notif


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


# --- Tests: GET /config/rating-weights ---


class TestGetRatingWeights:
    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_config(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/rating-weights")

        assert response.status_code == 200
        data = response.json()
        assert data["revenue_weight"] == 20
        assert data["cs_weight"] == 20
        assert data["products_weight"] == 25
        assert data["extras_weight"] == 25
        assert data["reviews_weight"] == 10
        assert data["prize_gold_pct"] == 0.5

    @pytest.mark.asyncio
    async def test_returns_config_from_db(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        config = make_rating_config()
        result = MagicMock()
        result.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/rating-weights")

        assert response.status_code == 200
        data = response.json()
        assert data["revenue_weight"] == 30
        assert data["extra_services"] == ["воск", "массаж"]

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/rating-weights")

        assert response.status_code in (401, 403)


# --- Tests: PUT /config/rating-weights ---


class TestPutRatingWeights:
    @pytest.mark.asyncio
    async def test_owner_can_update(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        # UPSERT execute
        upsert_result = MagicMock()
        # branches for cache invalidation
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = []
        # get_rating_config after
        config = make_rating_config()
        config.revenue_weight = 40
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        mock_db.execute = AsyncMock(side_effect=[upsert_result, branches_result, config_result])
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/rating-weights",
                json={
                    "revenue_weight": 40,
                    "cs_weight": 10,
                    "products_weight": 20,
                    "extras_weight": 20,
                    "reviews_weight": 10,
                    "prize_gold_pct": 0.5,
                    "prize_silver_pct": 0.3,
                    "prize_bronze_pct": 0.1,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["revenue_weight"] == 40

    @pytest.mark.asyncio
    async def test_barber_cannot_update_403(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/rating-weights",
                json={
                    "revenue_weight": 20,
                    "cs_weight": 20,
                    "products_weight": 25,
                    "extras_weight": 25,
                    "reviews_weight": 10,
                    "prize_gold_pct": 0.5,
                    "prize_silver_pct": 0.3,
                    "prize_bronze_pct": 0.1,
                },
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_weights_must_sum_to_100_422(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/rating-weights",
                json={
                    "revenue_weight": 50,
                    "cs_weight": 50,
                    "products_weight": 50,
                    "extras_weight": 0,
                    "reviews_weight": 0,
                    "prize_gold_pct": 0.5,
                    "prize_silver_pct": 0.3,
                    "prize_bronze_pct": 0.1,
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_weight_422(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/rating-weights",
                json={
                    "revenue_weight": -10,
                    "cs_weight": 20,
                    "products_weight": 25,
                    "extras_weight": 25,
                    "reviews_weight": 10,
                    "prize_gold_pct": 0.5,
                    "prize_silver_pct": 0.3,
                    "prize_bronze_pct": 0.1,
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_prize_pcts_exceed_1_422(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/rating-weights",
                json={
                    "revenue_weight": 20,
                    "cs_weight": 20,
                    "products_weight": 25,
                    "extras_weight": 25,
                    "reviews_weight": 10,
                    "prize_gold_pct": 0.5,
                    "prize_silver_pct": 0.3,
                    "prize_bronze_pct": 0.3,
                },
            )

        assert response.status_code == 422


# --- Tests: GET/PUT /config/pvr-thresholds ---


class TestPVRThresholds:
    @pytest.mark.asyncio
    async def test_get_defaults_when_no_config(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/pvr-thresholds")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 6
        assert data["thresholds"][0]["amount"] == 30_000_000
        assert data["count_products"] is False

    @pytest.mark.asyncio
    async def test_get_custom_config(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        config = make_pvr_config()
        result = MagicMock()
        result.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/pvr-thresholds")

        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 2
        assert data["count_products"] is True

    @pytest.mark.asyncio
    async def test_put_owner_can_update(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        upsert_result = MagicMock()
        config = make_pvr_config()
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        mock_db.execute = AsyncMock(side_effect=[upsert_result, config_result])
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/pvr-thresholds",
                json={
                    "thresholds": [
                        {"amount": 30_000_000, "bonus": 1_000_000},
                        {"amount": 50_000_000, "bonus": 3_000_000},
                    ],
                    "count_products": True,
                    "count_certificates": False,
                },
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_non_ascending_thresholds_422(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/pvr-thresholds",
                json={
                    "thresholds": [
                        {"amount": 50_000_000, "bonus": 3_000_000},
                        {"amount": 30_000_000, "bonus": 1_000_000},
                    ],
                    "count_products": False,
                    "count_certificates": False,
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_thresholds_422(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/api/v1/config/pvr-thresholds",
                json={
                    "thresholds": [],
                    "count_products": False,
                    "count_certificates": False,
                },
            )

        assert response.status_code == 422


# --- Tests: Branch endpoints ---


class TestBranchEndpoints:
    @pytest.mark.asyncio
    async def test_list_branches(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch = make_branch_model()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [branch]
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/branches")

        assert response.status_code == 200
        data = response.json()
        assert len(data["branches"]) == 1
        assert data["branches"][0]["name"] == "Main Branch"

    @pytest.mark.asyncio
    async def test_create_branch_201(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_db.commit = AsyncMock()

        async def fake_refresh(obj):
            obj.id = BRANCH_ID
            obj.organization_id = ORG_ID
            obj.is_active = True
            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/config/branches",
                json={"name": "New Branch", "address": "456 Oak Ave"},
            )

        assert response.status_code == 201
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_branch_not_found_404(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/config/branches/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_barber_cannot_access_403(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/branches")

        assert response.status_code == 403


# --- Tests: User endpoints ---


class TestUserEndpoints:
    @pytest.mark.asyncio
    async def test_list_users(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        db_user = make_user_model()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [db_user]
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/users")

        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 1
        assert data["users"][0]["name"] == "Pavel"

    @pytest.mark.asyncio
    async def test_create_user_201(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_db.commit = AsyncMock()

        async def fake_refresh(obj):
            obj.id = USER_ID
            obj.organization_id = ORG_ID
            obj.is_active = True
            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/config/users",
                json={
                    "telegram_id": 999888777,
                    "name": "New Barber",
                    "role": "barber",
                    "branch_id": str(BRANCH_ID),
                },
            )

        assert response.status_code == 201
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_not_found_404(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/config/users/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_barber_cannot_manage_users_403(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/users")

        assert response.status_code == 403


# --- Tests: Notification endpoints ---


class TestNotificationEndpoints:
    @pytest.mark.asyncio
    async def test_list_notifications(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        notif = make_notif_model()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [notif]
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/notifications")

        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["notification_type"] == "daily_rating"

    @pytest.mark.asyncio
    async def test_create_notification_201(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_db.commit = AsyncMock()

        async def fake_refresh(obj):
            obj.id = NOTIF_ID
            obj.organization_id = ORG_ID
            obj.is_enabled = True
            obj.created_at = datetime.now(UTC)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/config/notifications",
                json={
                    "notification_type": "pvr_bell",
                    "telegram_chat_id": -100999888,
                },
            )

        assert response.status_code == 201
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_notification_204(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        notif = make_notif_model()
        result = MagicMock()
        result.scalar_one_or_none.return_value = notif
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/api/v1/config/notifications/{NOTIF_ID}")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_notification_not_found_404(self):
        user = make_user(role="owner")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/api/v1/config/notifications/{uuid.uuid4()}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_barber_cannot_manage_notifications_403(self):
        user = make_user(role="barber")

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/config/notifications")

        assert response.status_code == 403
