"""Tests for polling and full sync Celery tasks."""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.sync_tasks import _full_sync_all_branches, _poll_all_branches

# --- Helpers ---


def make_branch(name: str = "Branch 1", company_id: int = 555):
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = uuid.uuid4()
    branch.name = name
    branch.organization_id = uuid.uuid4()
    branch.yclients_company_id = company_id
    branch.is_active = True
    return branch


def mock_db_with_branches(branches):
    """Create a mock async session that returns given branches."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = branches

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    return mock_session


# Patch targets at source modules (lazy imports inside functions)
PATCH_SESSION = "app.database.async_session"
PATCH_YCLIENTS = "app.integrations.yclients.client.YClientsClient"
PATCH_SYNC = "app.services.sync.SyncService"
PATCH_PLAN = "app.services.plans.PlanService"
PATCH_RATING = "app.services.rating.RatingEngine"


# --- Tests: _poll_all_branches ---


class TestPollAllBranches:
    @pytest.mark.asyncio
    @patch(PATCH_RATING)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_polls_all_active_branches(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls, mock_rating_cls
    ):
        branches = [make_branch("Branch 1", 555), make_branch("Branch 2", 666)]
        mock_db = mock_db_with_branches(branches)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_records = AsyncMock(return_value=3)
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock(return_value=None)
        mock_plan_cls.return_value = mock_plan

        mock_rating = AsyncMock()
        mock_rating.recalculate = AsyncMock(return_value=[])
        mock_rating_cls.return_value = mock_rating

        result = await _poll_all_branches()

        assert mock_sync.sync_records.call_count == 2
        assert result["branches_processed"] == 2
        assert result["total_synced"] == 6  # 3 per branch
        assert result["errors"] == 0
        mock_yclients.close.assert_called_once()
        # Plan progress updated for each branch with synced records
        assert mock_plan.update_progress.call_count == 2
        # Rating recalculated for each branch with synced records
        assert mock_rating.recalculate.call_count == 2

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_returns_zero_when_no_branches(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls
    ):
        mock_db = mock_db_with_branches([])
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync_cls.return_value = mock_sync

        mock_plan_cls.return_value = AsyncMock()

        result = await _poll_all_branches()

        assert result["branches_processed"] == 0
        assert result["total_synced"] == 0
        mock_sync.sync_records.assert_not_called()

    @pytest.mark.asyncio
    @patch(PATCH_RATING)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_handles_branch_error_gracefully(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls, mock_rating_cls
    ):
        branches = [make_branch("OK Branch"), make_branch("Bad Branch")]
        mock_db = mock_db_with_branches(branches)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_records = AsyncMock(
            side_effect=[5, RuntimeError("API down")]
        )
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock(return_value=None)
        mock_plan_cls.return_value = mock_plan

        mock_rating = AsyncMock()
        mock_rating.recalculate = AsyncMock(return_value=[])
        mock_rating_cls.return_value = mock_rating

        result = await _poll_all_branches()

        assert result["branches_processed"] == 1
        assert result["total_synced"] == 5
        assert result["errors"] == 1

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_uses_today_as_date_range(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls
    ):
        branches = [make_branch()]
        mock_db = mock_db_with_branches(branches)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_records = AsyncMock(return_value=0)
        mock_sync_cls.return_value = mock_sync

        mock_plan_cls.return_value = AsyncMock()

        await _poll_all_branches()

        call_args = mock_sync.sync_records.call_args
        assert call_args[0][1] == date.today()  # date_from
        assert call_args[0][2] == date.today()  # date_to


# --- Tests: _full_sync_all_branches ---


class TestFullSyncAllBranches:
    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_syncs_yesterday_for_all_branches(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls
    ):
        branches = [make_branch("Branch 1"), make_branch("Branch 2")]
        mock_db = mock_db_with_branches(branches)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_staff = AsyncMock(return_value=2)
        mock_sync.sync_records = AsyncMock(return_value=10)
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock(return_value=None)
        mock_plan_cls.return_value = mock_plan

        result = await _full_sync_all_branches()

        yesterday = date.today() - timedelta(days=1)

        # Verify sync_records called with yesterday
        for call in mock_sync.sync_records.call_args_list:
            assert call[0][1] == yesterday  # date_from
            assert call[0][2] == yesterday  # date_to

        assert result["date"] == str(yesterday)
        assert result["branches_processed"] == 2
        assert result["total_synced"] == 20  # 10 per branch
        assert result["staff_synced"] == 4  # 2 per branch
        assert result["errors"] == 0

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_syncs_staff_before_records(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls
    ):
        branches = [make_branch()]
        mock_db = mock_db_with_branches(branches)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        call_order = []
        mock_sync = AsyncMock()
        mock_sync.sync_staff = AsyncMock(
            side_effect=lambda *a, **kw: call_order.append("staff") or 1
        )
        mock_sync.sync_records = AsyncMock(
            side_effect=lambda *a, **kw: call_order.append("records") or 5
        )
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock(return_value=None)
        mock_plan_cls.return_value = mock_plan

        await _full_sync_all_branches()

        assert call_order == ["staff", "records"]

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_handles_branch_error_gracefully(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls
    ):
        branches = [make_branch("OK"), make_branch("Fail")]
        mock_db = mock_db_with_branches(branches)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_staff = AsyncMock(
            side_effect=[2, RuntimeError("staff error")]
        )
        mock_sync.sync_records = AsyncMock(return_value=10)
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock(return_value=None)
        mock_plan_cls.return_value = mock_plan

        result = await _full_sync_all_branches()

        assert result["branches_processed"] == 1
        assert result["errors"] == 1

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_closes_yclients_on_success(
        self, mock_sync_cls, mock_session_factory, mock_yclients_cls, mock_plan_cls
    ):
        mock_db = mock_db_with_branches([])
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync_cls.return_value = AsyncMock()

        mock_plan = AsyncMock()
        mock_plan_cls.return_value = mock_plan

        await _full_sync_all_branches()

        mock_yclients.close.assert_called_once()


# --- Tests: Celery task wrappers ---


class TestCeleryTaskWrappers:
    @patch("app.tasks.sync_tasks._poll_all_branches", new_callable=AsyncMock)
    def test_poll_task_calls_helper(self, mock_poll):
        mock_poll.return_value = {"total_synced": 5}

        from app.tasks.sync_tasks import poll_yclients

        result = poll_yclients.run()

        assert result["total_synced"] == 5

    @patch("app.tasks.sync_tasks._full_sync_all_branches", new_callable=AsyncMock)
    def test_full_sync_task_calls_helper(self, mock_sync):
        mock_sync.return_value = {"total_synced": 20}

        from app.tasks.sync_tasks import full_sync_yclients

        result = full_sync_yclients.run()

        assert result["total_synced"] == 20


# --- Tests: Beat schedule config ---


class TestBeatSchedule:
    def test_poll_schedule_defined(self):
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "poll-yclients-every-10-min" in schedule
        assert schedule["poll-yclients-every-10-min"]["task"] == "poll_yclients"

    def test_full_sync_schedule_defined(self):
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "full-sync-daily-4am" in schedule
        entry = schedule["full-sync-daily-4am"]
        assert entry["task"] == "full_sync_yclients"
