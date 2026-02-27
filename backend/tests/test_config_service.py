"""Tests for the Config service."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.config import ConfigService

# --- Helpers ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BRANCH_ID_2 = uuid.uuid4()
USER_ID = uuid.uuid4()
NOTIF_ID = uuid.uuid4()


def make_rating_config(org_id: uuid.UUID = ORG_ID) -> MagicMock:
    config = MagicMock()
    config.id = uuid.uuid4()
    config.organization_id = org_id
    config.revenue_weight = 20
    config.cs_weight = 20
    config.products_weight = 25
    config.extras_weight = 25
    config.reviews_weight = 10
    config.prize_gold_pct = 0.5
    config.prize_silver_pct = 0.3
    config.prize_bronze_pct = 0.1
    config.extra_services = None
    return config


def make_pvr_config(org_id: uuid.UUID = ORG_ID) -> MagicMock:
    config = MagicMock()
    config.id = uuid.uuid4()
    config.organization_id = org_id
    config.thresholds = [
        {"amount": 30_000_000, "bonus": 1_000_000},
        {"amount": 50_000_000, "bonus": 3_000_000},
    ]
    config.count_products = False
    config.count_certificates = False
    return config


def make_branch(
    branch_id: uuid.UUID = BRANCH_ID,
    org_id: uuid.UUID = ORG_ID,
    name: str = "Main Branch",
) -> MagicMock:
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = org_id
    branch.name = name
    branch.address = "123 Main St"
    branch.yclients_company_id = None
    branch.telegram_group_id = None
    branch.is_active = True
    return branch


def make_user(
    user_id: uuid.UUID = USER_ID,
    org_id: uuid.UUID = ORG_ID,
    branch_id: uuid.UUID = BRANCH_ID,
    name: str = "Pavel",
    role: str = "barber",
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.organization_id = org_id
    user.branch_id = branch_id
    user.telegram_id = 123456789
    user.role = role
    user.name = name
    user.grade = "senior"
    user.haircut_price = 200_000
    user.yclients_staff_id = None
    user.is_active = True
    return user


def make_notification(
    notif_id: uuid.UUID = NOTIF_ID,
    org_id: uuid.UUID = ORG_ID,
) -> MagicMock:
    notif = MagicMock()
    notif.id = notif_id
    notif.organization_id = org_id
    notif.branch_id = None
    notif.notification_type = "daily_rating"
    notif.telegram_chat_id = -1001234567890
    notif.is_enabled = True
    notif.schedule_time = None
    return notif


# --- Tests: Rating Config ---


class TestGetRatingConfig:
    @pytest.mark.asyncio
    async def test_returns_config_when_exists(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        config = make_rating_config()
        result = MagicMock()
        result.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_rating_config(ORG_ID)

        assert got is not None
        assert got.revenue_weight == 20

    @pytest.mark.asyncio
    async def test_returns_none_when_no_config(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_rating_config(ORG_ID)

        assert got is None


class TestUpsertRatingConfig:
    @pytest.mark.asyncio
    async def test_upserts_and_invalidates_caches(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        # execute for UPSERT
        upsert_result = MagicMock()
        # execute for get_rating_config after upsert
        config = make_rating_config()
        config.revenue_weight = 40
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config
        # execute for _invalidate_rating_caches (branch IDs query)
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [BRANCH_ID, BRANCH_ID_2]

        mock_db.execute = AsyncMock(side_effect=[upsert_result, branches_result, config_result])
        mock_db.commit = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        result = await service.upsert_rating_config(
            ORG_ID,
            {
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

        assert result.revenue_weight == 40
        mock_db.commit.assert_awaited_once()
        # Two branch caches should be invalidated
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_invalidates_with_correct_keys(self):
        """Verifies the exact cache keys being deleted."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        upsert_result = MagicMock()
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = [BRANCH_ID]
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = make_rating_config()

        mock_db.execute = AsyncMock(side_effect=[upsert_result, branches_result, config_result])
        mock_db.commit = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        await service.upsert_rating_config(ORG_ID, {"revenue_weight": 30})

        today = date.today()
        expected_key = f"rating:{BRANCH_ID}:{today}"
        mock_redis.delete.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_no_branches_no_cache_deletion(self):
        """When org has no active branches, no cache keys are deleted."""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        upsert_result = MagicMock()
        branches_result = MagicMock()
        branches_result.scalars.return_value.all.return_value = []
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = make_rating_config()

        mock_db.execute = AsyncMock(side_effect=[upsert_result, branches_result, config_result])
        mock_db.commit = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        await service.upsert_rating_config(ORG_ID, {"revenue_weight": 30})

        mock_redis.delete.assert_not_called()


# --- Tests: PVR Config ---


class TestGetPVRConfig:
    @pytest.mark.asyncio
    async def test_returns_config_when_exists(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        config = make_pvr_config()
        result = MagicMock()
        result.scalar_one_or_none.return_value = config
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_pvr_config(ORG_ID)

        assert got is not None
        assert len(got.thresholds) == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_no_config(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_pvr_config(ORG_ID)

        assert got is None


class TestUpsertPVRConfig:
    @pytest.mark.asyncio
    async def test_upserts_config(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        upsert_result = MagicMock()
        config = make_pvr_config()
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        mock_db.execute = AsyncMock(side_effect=[upsert_result, config_result])
        mock_db.commit = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        result = await service.upsert_pvr_config(
            ORG_ID,
            {
                "thresholds": [{"amount": 30_000_000, "bonus": 1_000_000}],
                "count_products": True,
                "count_certificates": False,
            },
        )

        assert result is not None
        mock_db.commit.assert_awaited_once()


# --- Tests: Branch CRUD ---


class TestBranchCRUD:
    @pytest.mark.asyncio
    async def test_list_branches(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch = make_branch()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [branch]
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        branches = await service.list_branches(ORG_ID)

        assert len(branches) == 1
        assert branches[0].name == "Main Branch"

    @pytest.mark.asyncio
    async def test_list_branches_empty(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        branches = await service.list_branches(ORG_ID)

        assert branches == []

    @pytest.mark.asyncio
    async def test_get_branch_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch = make_branch()
        result = MagicMock()
        result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_branch(ORG_ID, BRANCH_ID)

        assert got is not None
        assert got.id == BRANCH_ID

    @pytest.mark.asyncio
    async def test_get_branch_not_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_branch(ORG_ID, uuid.uuid4())

        assert got is None

    @pytest.mark.asyncio
    async def test_create_branch(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        await service.create_branch(ORG_ID, {"name": "New Branch", "address": "456 Oak Ave"})

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_branch(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        branch = make_branch()
        result = MagicMock()
        result.scalar_one_or_none.return_value = branch
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        updated = await service.update_branch(ORG_ID, BRANCH_ID, {"name": "Updated Branch"})

        assert updated is not None
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_branch_not_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        updated = await service.update_branch(ORG_ID, uuid.uuid4(), {"name": "X"})

        assert updated is None
        mock_db.commit.assert_not_awaited()


# --- Tests: User CRUD ---


class TestUserCRUD:
    @pytest.mark.asyncio
    async def test_list_users(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        user = make_user()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [user]
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        users = await service.list_users(ORG_ID)

        assert len(users) == 1
        assert users[0].name == "Pavel"

    @pytest.mark.asyncio
    async def test_list_users_with_branch_filter(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        user = make_user()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [user]
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        users = await service.list_users(ORG_ID, branch_id=BRANCH_ID)

        assert len(users) == 1
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        user = make_user()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_user(ORG_ID, USER_ID)

        assert got is not None
        assert got.id == USER_ID

    @pytest.mark.asyncio
    async def test_get_user_not_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        got = await service.get_user(ORG_ID, uuid.uuid4())

        assert got is None

    @pytest.mark.asyncio
    async def test_create_user(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        await service.create_user(
            ORG_ID,
            {"telegram_id": 999, "name": "New User", "role": "barber"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_user(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        user = make_user()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        updated = await service.update_user(ORG_ID, USER_ID, {"is_active": False})

        assert updated is not None
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        updated = await service.update_user(ORG_ID, uuid.uuid4(), {"name": "X"})

        assert updated is None
        mock_db.commit.assert_not_awaited()


# --- Tests: Notification Config CRUD ---


class TestNotificationCRUD:
    @pytest.mark.asyncio
    async def test_list_notifications(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        notif = make_notification()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [notif]
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        notifs = await service.list_notifications(ORG_ID)

        assert len(notifs) == 1
        assert notifs[0].notification_type == "daily_rating"

    @pytest.mark.asyncio
    async def test_list_notifications_by_branch(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        notifs = await service.list_notifications(ORG_ID, branch_id=BRANCH_ID)

        assert notifs == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_notification(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        service = ConfigService(db=mock_db, redis=mock_redis)
        await service.create_notification(
            ORG_ID,
            {
                "notification_type": "pvr_bell",
                "telegram_chat_id": -100999,
            },
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_notification(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        notif = make_notification()
        result = MagicMock()
        result.scalar_one_or_none.return_value = notif
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        updated = await service.update_notification(ORG_ID, NOTIF_ID, {"is_enabled": False})

        assert updated is not None
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_notification_not_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        updated = await service.update_notification(ORG_ID, uuid.uuid4(), {"is_enabled": False})

        assert updated is None
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_notification(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        notif = make_notification()
        result = MagicMock()
        result.scalar_one_or_none.return_value = notif
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        deleted = await service.delete_notification(ORG_ID, NOTIF_ID)

        assert deleted is True
        mock_db.delete.assert_awaited_once_with(notif)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_notification_not_found(self):
        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        service = ConfigService(db=mock_db, redis=mock_redis)
        deleted = await service.delete_notification(ORG_ID, uuid.uuid4())

        assert deleted is False
        mock_db.delete.assert_not_awaited()
        mock_db.commit.assert_not_awaited()


# --- Tests: Schema validation ---


class TestSchemaValidation:
    def test_weights_must_sum_to_100(self):
        from app.schemas.config import RatingWeightsRequest

        with pytest.raises(ValueError, match="sum to 100"):
            RatingWeightsRequest(
                revenue_weight=50,
                cs_weight=50,
                products_weight=50,
                extras_weight=0,
                reviews_weight=0,
                prize_gold_pct=0.5,
                prize_silver_pct=0.3,
                prize_bronze_pct=0.1,
            )

    def test_valid_weights_accepted(self):
        from app.schemas.config import RatingWeightsRequest

        req = RatingWeightsRequest(
            revenue_weight=30,
            cs_weight=20,
            products_weight=20,
            extras_weight=20,
            reviews_weight=10,
            prize_gold_pct=0.5,
            prize_silver_pct=0.3,
            prize_bronze_pct=0.1,
        )
        assert req.revenue_weight == 30

    def test_prize_pcts_over_1(self):
        from app.schemas.config import RatingWeightsRequest

        with pytest.raises(ValueError, match=r"<= 1\.0"):
            RatingWeightsRequest(
                revenue_weight=20,
                cs_weight=20,
                products_weight=25,
                extras_weight=25,
                reviews_weight=10,
                prize_gold_pct=0.5,
                prize_silver_pct=0.3,
                prize_bronze_pct=0.3,
            )

    def test_thresholds_not_ascending(self):
        from app.schemas.config import PVRThresholdsRequest, ThresholdEntry

        with pytest.raises(ValueError, match="ascending"):
            PVRThresholdsRequest(
                thresholds=[
                    ThresholdEntry(amount=50_000_000, bonus=3_000_000),
                    ThresholdEntry(amount=30_000_000, bonus=1_000_000),
                ],
                count_products=False,
                count_certificates=False,
            )

    def test_thresholds_empty_rejected(self):
        from app.schemas.config import PVRThresholdsRequest

        with pytest.raises(ValueError, match="At least one"):
            PVRThresholdsRequest(
                thresholds=[],
                count_products=False,
                count_certificates=False,
            )

    def test_valid_thresholds_accepted(self):
        from app.schemas.config import PVRThresholdsRequest, ThresholdEntry

        req = PVRThresholdsRequest(
            thresholds=[
                ThresholdEntry(amount=30_000_000, bonus=1_000_000),
                ThresholdEntry(amount=50_000_000, bonus=3_000_000),
            ],
            count_products=True,
            count_certificates=False,
        )
        assert len(req.thresholds) == 2
