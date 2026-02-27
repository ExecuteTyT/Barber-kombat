"""Tests for notification delivery Celery tasks."""

import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Test constants ---

ORG_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
REVIEW_ID = uuid.uuid4()


def _make_report(report_type: str, data: dict, delivered: bool = False):
    """Create a mock Report object."""
    report = MagicMock()
    report.id = uuid.uuid4()
    report.organization_id = ORG_ID
    report.branch_id = None
    report.type = report_type
    report.data = data
    report.delivered_telegram = delivered
    report.delivered_at = None
    return report


def _make_branch(branch_id=BRANCH_ID, telegram_group_id=-100123):
    """Create a mock Branch object."""
    branch = MagicMock()
    branch.id = branch_id
    branch.organization_id = ORG_ID
    branch.name = "8 марта"
    branch.telegram_group_id = telegram_group_id
    branch.is_active = True
    return branch


def _make_notif_config(notification_type, chat_id=-100999):
    """Create a mock NotificationConfig."""
    config = MagicMock()
    config.id = uuid.uuid4()
    config.organization_id = ORG_ID
    config.branch_id = None
    config.notification_type = notification_type
    config.telegram_chat_id = chat_id
    config.is_enabled = True
    return config


def _kombat_daily_report():
    return _make_report("kombat_daily", {
        "date": "2026-02-22",
        "branches": [
            {
                "branch_id": str(BRANCH_ID),
                "name": "8 марта",
                "standings": [
                    {"barber_id": str(uuid.uuid4()), "name": "Павел",
                     "rank": 1, "total_score": 95.5, "revenue": 1_350_000},
                ],
            }
        ],
    })


def _revenue_report():
    return _make_report("daily_revenue", {
        "date": "2026-02-22",
        "branches": [
            {
                "branch_id": str(BRANCH_ID),
                "name": "8 марта",
                "revenue_today": 850_000,
                "revenue_mtd": 18_500_000,
                "plan_target": 24_000_000,
                "plan_percentage": 77.1,
                "barbers_in_shift": 8,
                "barbers_total": 10,
            }
        ],
        "network_total_today": 2_530_000,
        "network_total_mtd": 55_000_000,
    })


# ------------------------------------------------------------------
# Tests: _send_to_notif_targets
# ------------------------------------------------------------------


class TestSendToNotifTargets:
    @pytest.mark.asyncio
    async def test_sends_to_enabled_targets(self):
        from app.tasks.notification_tasks import _send_to_notif_targets

        mock_db = AsyncMock()
        mock_bot = AsyncMock()

        config = _make_notif_config("daily_rating", chat_id=-100111)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [config]
        mock_db.execute = AsyncMock(return_value=result_mock)

        send_fn = AsyncMock(return_value=True)

        sent = await _send_to_notif_targets(
            mock_db, mock_bot, ORG_ID, "daily_rating", branch_id=BRANCH_ID,
            send_fn=send_fn,
        )

        assert sent == 1
        send_fn.assert_awaited_once_with(-100111)

    @pytest.mark.asyncio
    async def test_no_targets_returns_zero(self):
        from app.tasks.notification_tasks import _send_to_notif_targets

        mock_db = AsyncMock()
        mock_bot = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        send_fn = AsyncMock(return_value=True)

        sent = await _send_to_notif_targets(
            mock_db, mock_bot, ORG_ID, "daily_rating", branch_id=None,
            send_fn=send_fn,
        )

        assert sent == 0
        send_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handles_send_failure(self):
        from app.tasks.notification_tasks import _send_to_notif_targets

        mock_db = AsyncMock()
        mock_bot = AsyncMock()

        config = _make_notif_config("daily_rating")
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [config]
        mock_db.execute = AsyncMock(return_value=result_mock)

        send_fn = AsyncMock(side_effect=Exception("Send failed"))

        sent = await _send_to_notif_targets(
            mock_db, mock_bot, ORG_ID, "daily_rating", branch_id=None,
            send_fn=send_fn,
        )

        assert sent == 0

    @pytest.mark.asyncio
    async def test_multiple_targets(self):
        from app.tasks.notification_tasks import _send_to_notif_targets

        mock_db = AsyncMock()
        mock_bot = AsyncMock()

        configs = [
            _make_notif_config("pvr_threshold", chat_id=-100111),
            _make_notif_config("pvr_threshold", chat_id=-100222),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = configs
        mock_db.execute = AsyncMock(return_value=result_mock)

        send_fn = AsyncMock(return_value=True)

        sent = await _send_to_notif_targets(
            mock_db, mock_bot, ORG_ID, "pvr_threshold", branch_id=BRANCH_ID,
            send_fn=send_fn,
        )

        assert sent == 2
        assert send_fn.await_count == 2


# ------------------------------------------------------------------
# Tests: _send_kombat_daily
# ------------------------------------------------------------------


class TestSendKombatDaily:
    @pytest.mark.asyncio
    async def test_sends_to_branch_group(self):
        from app.tasks.notification_tasks import _send_kombat_daily

        report = _kombat_daily_report()

        mock_db = AsyncMock()
        branch = _make_branch()

        # First call: get branch; second call: get notif configs
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        notif_result = MagicMock()
        notif_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[branch_result, notif_result])

        mock_bot = MagicMock()
        mock_bot.send_kombat_report = AsyncMock(return_value=True)

        sent = await _send_kombat_daily(mock_db, mock_bot, report)

        assert sent >= 1
        mock_bot.send_kombat_report.assert_awaited_once()
        call_kwargs = mock_bot.send_kombat_report.call_args.kwargs
        assert call_kwargs["chat_id"] == -100123

    @pytest.mark.asyncio
    async def test_skips_branch_without_telegram_group(self):
        from app.tasks.notification_tasks import _send_kombat_daily

        report = _kombat_daily_report()

        mock_db = AsyncMock()
        branch = _make_branch(telegram_group_id=None)

        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch
        notif_result = MagicMock()
        notif_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[branch_result, notif_result])

        mock_bot = MagicMock()
        mock_bot.send_kombat_report = AsyncMock(return_value=True)

        sent = await _send_kombat_daily(mock_db, mock_bot, report)

        assert sent == 0
        mock_bot.send_kombat_report.assert_not_awaited()


# ------------------------------------------------------------------
# Tests: _send_revenue
# ------------------------------------------------------------------


class TestSendRevenue:
    @pytest.mark.asyncio
    async def test_sends_via_notif_targets(self):
        from app.tasks.notification_tasks import _send_revenue

        report = _revenue_report()

        mock_db = AsyncMock()
        config = _make_notif_config("daily_revenue", chat_id=-100555)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [config]
        mock_db.execute = AsyncMock(return_value=result_mock)

        mock_bot = MagicMock()
        mock_bot.send_revenue_report = AsyncMock(return_value=True)

        sent = await _send_revenue(mock_db, mock_bot, report)

        assert sent == 1


# ------------------------------------------------------------------
# Tests: PVR bell notification
# ------------------------------------------------------------------


class TestPVRBellNotification:
    @pytest.mark.asyncio
    async def test_sends_to_branch_and_targets(self):
        from app.tasks.notification_tasks import _send_pvr_bell_notification

        branch = _make_branch()
        config = _make_notif_config("pvr_threshold", chat_id=-100222)

        with patch("app.database.async_session") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First execute: get branch; second: get notif configs
            branch_result = MagicMock()
            branch_result.scalar_one_or_none.return_value = branch
            notif_result = MagicMock()
            notif_result.scalars.return_value.all.return_value = [config]
            mock_db.execute = AsyncMock(side_effect=[branch_result, notif_result])

            with patch("app.integrations.telegram.bot.TelegramBot") as MockBot:
                mock_bot = MagicMock()
                mock_bot.send_pvr_bell = AsyncMock(return_value=True)
                MockBot.return_value = mock_bot

                result = await _send_pvr_bell_notification(
                    organization_id=str(ORG_ID),
                    branch_id=str(BRANCH_ID),
                    barber_name="Павел",
                    threshold=50_000_000,
                    bonus=3_000_000,
                )

                assert result["sent"] >= 1
                mock_bot.send_pvr_bell.assert_awaited()


# ------------------------------------------------------------------
# Tests: Negative review notification
# ------------------------------------------------------------------


class TestNegativeReviewNotification:
    @pytest.mark.asyncio
    async def test_sends_to_configured_targets(self):
        from app.tasks.notification_tasks import _send_negative_review_notification

        config = _make_notif_config("negative_review", chat_id=-100333)

        with patch("app.database.async_session") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            notif_result = MagicMock()
            notif_result.scalars.return_value.all.return_value = [config]
            mock_db.execute = AsyncMock(return_value=notif_result)

            with patch("app.integrations.telegram.bot.TelegramBot") as MockBot:
                mock_bot = MagicMock()
                mock_bot.send_negative_review = AsyncMock(return_value=True)
                MockBot.return_value = mock_bot

                result = await _send_negative_review_notification(
                    organization_id=str(ORG_ID),
                    branch_name="8 марта",
                    barber_name="Павел",
                    client_name="Иван",
                    rating=2,
                    comment="Плохая стрижка",
                    created_at="2026-02-22 15:30",
                    review_id=str(REVIEW_ID),
                    branch_id=str(BRANCH_ID),
                )

                assert result["sent"] == 1
                mock_bot.send_negative_review.assert_awaited_once()


# ------------------------------------------------------------------
# Tests: Deliver daily reports flow
# ------------------------------------------------------------------


class TestDeliverDailyReports:
    @pytest.mark.asyncio
    async def test_marks_reports_as_delivered(self):
        from app.tasks.notification_tasks import _deliver_daily_reports

        report = _kombat_daily_report()
        branch = _make_branch()

        with patch("app.database.async_session") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First execute: get undelivered reports
            reports_result = MagicMock()
            reports_result.scalars.return_value.all.return_value = [report]
            # Second execute: get branch for kombat report
            branch_result = MagicMock()
            branch_result.scalar_one_or_none.return_value = branch
            # Third execute: get notif configs for branch
            notif_result = MagicMock()
            notif_result.scalars.return_value.all.return_value = []
            # Fourth execute: update report as delivered
            update_result = MagicMock()

            mock_db.execute = AsyncMock(
                side_effect=[reports_result, branch_result, notif_result, update_result]
            )
            mock_db.commit = AsyncMock()

            with patch("app.integrations.telegram.bot.TelegramBot") as MockBot:
                mock_bot = MagicMock()
                mock_bot.send_kombat_report = AsyncMock(return_value=True)
                MockBot.return_value = mock_bot

                result = await _deliver_daily_reports()

                assert result["reports_processed"] == 1
                assert result["sent"] >= 1
                # Verify commit was called (marking delivery)
                mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_undelivered_reports(self):
        from app.tasks.notification_tasks import _deliver_daily_reports

        with patch("app.database.async_session") as mock_session_cls:
            mock_db = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            reports_result = MagicMock()
            reports_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=reports_result)

            with patch("app.integrations.telegram.bot.TelegramBot"):
                result = await _deliver_daily_reports()

                assert result["reports_processed"] == 0
                assert result["sent"] == 0


# ------------------------------------------------------------------
# Tests: Celery beat schedule
# ------------------------------------------------------------------


class TestCeleryBeatSchedule:
    def test_notification_tasks_in_schedule(self):
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        assert "deliver-daily-notifications" in schedule
        assert schedule["deliver-daily-notifications"]["task"] == "deliver_daily_notifications"

        assert "deliver-day-to-day-notifications" in schedule
        assert schedule["deliver-day-to-day-notifications"]["task"] == "deliver_day_to_day_notifications"

        assert "deliver-monthly-notifications" in schedule
        assert schedule["deliver-monthly-notifications"]["task"] == "deliver_monthly_notifications"
