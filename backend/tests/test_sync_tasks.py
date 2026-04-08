"""Tests for polling and full sync Celery tasks."""

import uuid
from contextlib import asynccontextmanager
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


def _make_mock_db(branches, extra_rows=None):
    """Create a mock async session that returns `branches` for the first
    `execute(...)` call and `extra_rows` (or empty list) for subsequent ones.

    The result mock is always the same, so tests can tweak
    `scalars.return_value.all.return_value` directly if needed.
    """
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = branches

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    return mock_session


def make_task_sessionmaker_mock(db):
    """Build a drop-in replacement for `app.database.task_sessionmaker`.

    The real implementation is an async context manager that yields an
    `async_sessionmaker`. Callers then do::

        async with task_sessionmaker() as Session:
            async with Session() as db:
                ...

    We return a factory that, when called, yields a `Session` callable; each
    `Session()` call returns an async context manager that resolves to `db`.
    """

    @asynccontextmanager
    async def fake_task_sessionmaker():
        def session_factory():
            mgr = MagicMock()
            mgr.__aenter__ = AsyncMock(return_value=db)
            mgr.__aexit__ = AsyncMock(return_value=False)
            return mgr

        yield session_factory

    return fake_task_sessionmaker


# Patch targets at source modules (lazy imports inside task functions)
PATCH_TASK_SESSIONMAKER = "app.database.task_sessionmaker"
PATCH_YCLIENTS = "app.integrations.yclients.client.YClientsClient"
PATCH_SYNC = "app.services.sync.SyncService"
PATCH_PLAN = "app.services.plans.PlanService"
PATCH_PVR = "app.services.pvr.PVRService"
PATCH_RATING = "app.services.rating.RatingEngine"
PATCH_REPORTS = "app.services.reports.ReportService"


# --- Tests: _poll_all_branches ---


class TestPollAllBranches:
    @pytest.mark.asyncio
    @patch(PATCH_RATING)
    @patch(PATCH_PVR)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_polls_all_active_branches(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
        mock_pvr_cls,
        mock_rating_cls,
    ):
        branches = [make_branch("Branch 1", 555), make_branch("Branch 2", 666)]
        mock_db = _make_mock_db(branches)
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_records = AsyncMock(return_value=3)
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock(return_value=None)
        mock_plan_cls.return_value = mock_plan

        mock_pvr = AsyncMock()
        mock_pvr.recalculate_branch = AsyncMock(return_value=None)
        mock_pvr_cls.return_value = mock_pvr

        mock_rating = AsyncMock()
        mock_rating.recalculate = AsyncMock(return_value=[])
        mock_rating_cls.return_value = mock_rating

        result = await _poll_all_branches()

        assert mock_sync.sync_records.call_count == 2
        assert result["branches_processed"] == 2
        assert result["total_synced"] == 6  # 3 per branch
        assert result["errors"] == 0
        mock_yclients.close.assert_called_once()
        assert mock_plan.update_progress.call_count == 2
        assert mock_pvr.recalculate_branch.call_count == 2
        assert mock_rating.recalculate.call_count == 2

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_returns_zero_when_no_branches(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
    ):
        mock_db = _make_mock_db([])
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

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
    @patch(PATCH_PVR)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_handles_branch_error_gracefully(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
        mock_pvr_cls,
        mock_rating_cls,
    ):
        """One branch raising must not stop processing the others — a key
        regression: before the per-branch session fix, a single failure
        poisoned the whole polling cycle.
        """
        branches = [make_branch("OK Branch"), make_branch("Bad Branch")]
        mock_db = _make_mock_db(branches)
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

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

        mock_pvr = AsyncMock()
        mock_pvr.recalculate_branch = AsyncMock(return_value=None)
        mock_pvr_cls.return_value = mock_pvr

        mock_rating = AsyncMock()
        mock_rating.recalculate = AsyncMock(return_value=[])
        mock_rating_cls.return_value = mock_rating

        result = await _poll_all_branches()

        assert result["branches_processed"] == 1
        assert result["total_synced"] == 5
        assert result["errors"] == 1
        # Both branches were attempted
        assert mock_sync.sync_records.call_count == 2

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_uses_today_as_date_range(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
    ):
        branches = [make_branch()]
        mock_db = _make_mock_db(branches)
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

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
    @patch(PATCH_REPORTS)
    @patch(PATCH_RATING)
    @patch(PATCH_PVR)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_syncs_yesterday_for_all_branches(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
        mock_pvr_cls,
        mock_rating_cls,
        mock_reports_cls,
    ):
        branches = [make_branch("Branch 1"), make_branch("Branch 2")]
        mock_db = _make_mock_db(branches)
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_staff = AsyncMock(return_value=2)
        mock_sync.sync_records = AsyncMock(return_value=10)
        mock_sync_cls.return_value = mock_sync

        mock_plan_cls.return_value = AsyncMock()
        mock_pvr_cls.return_value = AsyncMock()
        mock_rating_cls.return_value = AsyncMock()
        mock_reports_cls.return_value = AsyncMock()

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
    @patch(PATCH_REPORTS)
    @patch(PATCH_RATING)
    @patch(PATCH_PVR)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_syncs_staff_before_records(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
        mock_pvr_cls,
        mock_rating_cls,
        mock_reports_cls,
    ):
        branches = [make_branch()]
        mock_db = _make_mock_db(branches)
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

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

        mock_plan_cls.return_value = AsyncMock()
        mock_pvr_cls.return_value = AsyncMock()
        mock_rating_cls.return_value = AsyncMock()
        mock_reports_cls.return_value = AsyncMock()

        await _full_sync_all_branches()

        # Within a single branch: staff must come before records. Cascade
        # recalcs run in a second pass after all branches finish syncing.
        staff_idx = call_order.index("staff")
        records_idx = call_order.index("records")
        assert staff_idx < records_idx

    @pytest.mark.asyncio
    @patch(PATCH_REPORTS)
    @patch(PATCH_RATING)
    @patch(PATCH_PVR)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_handles_branch_error_gracefully(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
        mock_pvr_cls,
        mock_rating_cls,
        mock_reports_cls,
    ):
        branches = [make_branch("OK"), make_branch("Fail")]
        mock_db = _make_mock_db(branches)
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_staff = AsyncMock(
            side_effect=[2, RuntimeError("staff error")]
        )
        mock_sync.sync_records = AsyncMock(return_value=10)
        mock_sync_cls.return_value = mock_sync

        mock_plan_cls.return_value = AsyncMock()
        mock_pvr_cls.return_value = AsyncMock()
        mock_rating_cls.return_value = AsyncMock()
        mock_reports_cls.return_value = AsyncMock()

        result = await _full_sync_all_branches()

        assert result["branches_processed"] == 1
        assert result["errors"] == 1

    @pytest.mark.asyncio
    @patch(PATCH_REPORTS)
    @patch(PATCH_RATING)
    @patch(PATCH_PVR)
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_TASK_SESSIONMAKER)
    @patch(PATCH_SYNC)
    async def test_closes_yclients_on_success(
        self,
        mock_sync_cls,
        mock_task_sessionmaker,
        mock_yclients_cls,
        mock_plan_cls,
        mock_pvr_cls,
        mock_rating_cls,
        mock_reports_cls,
    ):
        mock_db = _make_mock_db([])
        mock_task_sessionmaker.side_effect = make_task_sessionmaker_mock(mock_db)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync_cls.return_value = AsyncMock()
        mock_plan_cls.return_value = AsyncMock()
        mock_pvr_cls.return_value = AsyncMock()
        mock_rating_cls.return_value = AsyncMock()
        mock_reports_cls.return_value = AsyncMock()

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
