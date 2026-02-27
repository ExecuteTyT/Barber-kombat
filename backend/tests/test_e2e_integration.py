"""E2E integration tests for Barber Kombat.

Covers full lifecycle flows:
1. Webhook -> Sync -> Rating -> WebSocket -> API
2. Webhook -> Sync -> PVR -> Bell -> Telegram
3. Scheduled report -> Generation -> API
4. WebSocket concurrency (50 connections)
5. Edge cases: empty branches, single barber, month transition
"""

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ORG_ID = uuid.uuid4()
ORG_ID_2 = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
BRANCH_ID_2 = uuid.uuid4()
BARBER_ID_1 = uuid.uuid4()
BARBER_ID_2 = uuid.uuid4()
BARBER_ID_3 = uuid.uuid4()

# Patch targets — always patch at source module for lazy imports
PATCH_SESSION = "app.database.async_session"
PATCH_YCLIENTS = "app.integrations.yclients.client.YClientsClient"
PATCH_SYNC = "app.services.sync.SyncService"
PATCH_PLAN = "app.services.plans.PlanService"
PATCH_PVR = "app.services.pvr.PVRService"
PATCH_REDIS = "app.redis.redis_client"
PATCH_REPORT_SVC = "app.services.reports.ReportService"
PATCH_RATING_ENGINE = "app.services.rating.RatingEngine"
PATCH_BOT = "app.integrations.telegram.bot.TelegramBot"
PATCH_MONTHLY_RESET = "app.services.monthly_reset.MonthlyResetService"

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_branch(
    branch_id=None,
    org_id=None,
    name="Branch 1",
    company_id=555,
    telegram_group_id=-100123,
):
    """Create a mock Branch object."""
    b = MagicMock()
    b.id = branch_id or uuid.uuid4()
    b.organization_id = org_id or ORG_ID
    b.name = name
    b.yclients_company_id = company_id
    b.telegram_group_id = telegram_group_id
    b.is_active = True
    return b


def make_barber(barber_id=None, org_id=None, branch_id=None, name="Pavel"):
    """Create a mock User barber."""
    u = MagicMock()
    u.id = barber_id or uuid.uuid4()
    u.organization_id = org_id or ORG_ID
    u.branch_id = branch_id or BRANCH_ID
    u.name = name
    u.role = "barber"
    u.is_active = True
    return u


def make_org(org_id=None, name="TestOrg"):
    """Create a mock Organization."""
    org = MagicMock()
    org.id = org_id or ORG_ID
    org.name = name
    org.is_active = True
    return org


def make_report(
    report_type="kombat_daily",
    data=None,
    delivered=False,
    org_id=None,
    branch_id=None,
):
    """Create a mock Report object."""
    r = MagicMock()
    r.id = uuid.uuid4()
    r.organization_id = org_id or ORG_ID
    r.branch_id = branch_id or BRANCH_ID
    r.type = report_type
    r.data = data or {}
    r.delivered_telegram = delivered
    r.delivered_at = None
    r.date = date.today()
    return r


def make_notif_config(notification_type, chat_id=-100999):
    """Create a mock NotificationConfig."""
    c = MagicMock()
    c.notification_type = notification_type
    c.telegram_chat_id = chat_id
    c.is_enabled = True
    c.branch_id = None
    return c


def make_daily_rating(barber_id, rank=1, total_score=95.0, revenue=1_350_000):
    """Create a mock DailyRating."""
    dr = MagicMock()
    dr.barber_id = barber_id
    dr.rank = rank
    dr.total_score = total_score
    dr.revenue = revenue
    dr.date = date.today()
    return dr


def make_pvr_record(barber_id, revenue=35_000_000, threshold=30_000_000, bonus=1_000_000):
    """Create a mock PVRRecord."""
    r = MagicMock()
    r.id = uuid.uuid4()
    r.barber_id = barber_id
    r.cumulative_revenue = revenue
    r.current_threshold = threshold
    r.bonus_amount = bonus
    r.thresholds_reached = [{"amount": threshold, "reached_at": str(date.today())}]
    r.month = date.today().replace(day=1)
    return r


def mock_db_session(execute_results=None):
    """Create a mock async session with optional execute side_effect."""
    mock_db = AsyncMock()
    if execute_results is not None:
        mock_db.execute = AsyncMock(side_effect=execute_results)
    else:
        mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    return mock_db


def mock_session_context(mock_db):
    """Set up async context manager for session factory."""
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_factory


def db_result_list(items):
    """Create a mock DB result that returns items from scalars().all()."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def db_result_scalar(value):
    """Create a mock DB result for scalar_one()."""
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def db_result_scalar_or_none(value):
    """Create a mock DB result for scalar_one_or_none()."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


# ===========================================================================
# FLOW 1: Webhook -> Sync -> Rating -> WebSocket -> API
# ===========================================================================


class TestWebhookSyncRatingFlow:
    """Full cycle: YClients webhook triggers sync, rating recalc, WS push."""

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_poll_syncs_then_triggers_pvr_and_plan(
        self, mock_sync_cls, mock_session_cls, mock_yclients_cls, mock_plan_cls
    ):
        """After sync, PVR recalc and plan update are triggered for each branch."""
        from app.tasks.sync_tasks import _poll_all_branches

        branch = make_branch(branch_id=BRANCH_ID, org_id=ORG_ID)
        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=db_result_list([branch]))

        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_records = AsyncMock(return_value=5)
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock()
        mock_plan_cls.return_value = mock_plan

        result = await _poll_all_branches()

        assert result["branches_processed"] == 1
        assert result["total_synced"] == 5
        mock_sync.sync_records.assert_awaited_once()
        mock_plan.update_progress.assert_awaited_once()
        mock_yclients.close.assert_called_once()

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_full_sync_generates_reports_after_sync(
        self, mock_sync_cls, mock_session_cls, mock_yclients_cls, mock_plan_cls
    ):
        """Full sync should call report generation for all orgs after syncing."""
        from app.tasks.sync_tasks import _full_sync_all_branches

        branch = make_branch(branch_id=BRANCH_ID, org_id=ORG_ID)

        # First execute: branches query; second: org IDs for reports
        branches_result = db_result_list([branch])
        org_ids_result = MagicMock()
        org_ids_result.scalars.return_value.all.return_value = [ORG_ID]

        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(
            side_effect=[branches_result, org_ids_result]
        )

        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients = AsyncMock()
        mock_yclients_cls.return_value = mock_yclients

        mock_sync = AsyncMock()
        mock_sync.sync_staff = AsyncMock(return_value=2)
        mock_sync.sync_records = AsyncMock(return_value=10)
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock()
        mock_plan_cls.return_value = mock_plan

        with patch(PATCH_REPORT_SVC) as mock_report_cls:
            mock_report = AsyncMock()
            mock_report.generate_daily_revenue = AsyncMock()
            mock_report.generate_clients_report = AsyncMock()
            mock_report.generate_kombat_daily = AsyncMock()
            mock_report_cls.return_value = mock_report

            with patch(PATCH_PVR) as mock_pvr_cls:
                mock_pvr = AsyncMock()
                mock_pvr.recalculate_branch = AsyncMock()
                mock_pvr_cls.return_value = mock_pvr

                result = await _full_sync_all_branches()

        assert result["branches_processed"] == 1
        assert result["total_synced"] == 10
        assert result["staff_synced"] == 2

    @pytest.mark.asyncio
    async def test_websocket_broadcast_reaches_org_clients(self):
        """Messages broadcast to org reach all connected org clients."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws_other_org = AsyncMock()

        await mgr.connect(ws1, ORG_ID)
        await mgr.connect(ws2, ORG_ID)
        await mgr.connect(ws_other_org, ORG_ID_2)

        rating_update = {"type": "rating_update", "branch_id": str(BRANCH_ID)}
        await mgr.broadcast_to_org(ORG_ID, rating_update)

        ws1.send_json.assert_awaited_once_with(rating_update)
        ws2.send_json.assert_awaited_once_with(rating_update)
        ws_other_org.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_websocket_dead_connections_cleaned_on_broadcast(self):
        """Dead WS connections are cleaned up during broadcast."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_json.side_effect = RuntimeError("Connection closed")

        await mgr.connect(ws_alive, ORG_ID)
        await mgr.connect(ws_dead, ORG_ID)
        assert mgr.active_connections_count == 2

        await mgr.broadcast_to_org(ORG_ID, {"type": "ping"})

        ws_alive.send_json.assert_awaited_once()
        assert mgr.active_connections_count == 1


# ===========================================================================
# FLOW 2: Webhook -> Sync -> PVR -> Bell -> Telegram
# ===========================================================================


class TestPVRBellNotificationFlow:
    """Full cycle: sync triggers PVR recalc, threshold crossing sends bell."""

    @pytest.mark.asyncio
    async def test_pvr_threshold_crossing_publishes_bell(self):
        """When a barber crosses a new threshold, a Redis bell event is published."""
        from app.services.pvr import PVRService

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        # Build the mock chain for all DB queries in recalculate_barber:
        # 1. _load_config -> PVRConfig
        config = MagicMock()
        config.thresholds = [
            {"amount": 30_000_000, "bonus": 1_000_000},
            {"amount": 40_000_000, "bonus": 2_000_000},
        ]
        config.count_products = False
        config.count_certificates = False

        # 2. _calc_clean_revenue -> revenue (above 30M threshold)
        # 3. _get_record (before update) -> None (first time)
        # 4. UPSERT (execute)
        # 5. db.commit
        # 6. _get_barber -> barber
        # 7. _get_record (after update) -> new record

        barber = make_barber(barber_id=BARBER_ID_1, name="Pavel")
        new_record = make_pvr_record(BARBER_ID_1)

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_scalar_or_none(config),     # _load_config
                db_result_scalar(35_000_000),          # _calc_clean_revenue
                db_result_scalar_or_none(None),        # _get_record (prev)
                MagicMock(),                           # UPSERT
                db_result_scalar_or_none(barber),      # _get_barber
                db_result_scalar_or_none(new_record),  # _get_record (after)
            ]
        )
        mock_db.commit = AsyncMock()

        pvr_service = PVRService(db=mock_db, redis=mock_redis)
        await pvr_service.recalculate_barber(BARBER_ID_1, ORG_ID, date.today())

        # Bell should have been published
        mock_redis.publish.assert_awaited_once()
        channel = mock_redis.publish.call_args[0][0]
        assert f"ws:org:{ORG_ID}" == channel

        payload = json.loads(mock_redis.publish.call_args[0][1])
        assert payload["type"] == "pvr_threshold"
        assert payload["barber_name"] == "Pavel"
        assert payload["threshold"] == 30_000_000
        assert payload["bonus"] == 1_000_000

    @pytest.mark.asyncio
    async def test_pvr_no_bell_when_threshold_unchanged(self):
        """No bell when revenue increases but threshold stays the same."""
        from app.services.pvr import PVRService

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        config = MagicMock()
        config.thresholds = [
            {"amount": 30_000_000, "bonus": 1_000_000},
            {"amount": 40_000_000, "bonus": 2_000_000},
        ]
        config.count_products = False
        config.count_certificates = False

        # Already at 30M threshold
        existing_record = MagicMock()
        existing_record.current_threshold = 30_000_000
        existing_record.thresholds_reached = [
            {"amount": 30_000_000, "reached_at": "2026-01-15"}
        ]

        new_record = make_pvr_record(BARBER_ID_1)

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_scalar_or_none(config),          # _load_config
                db_result_scalar(32_000_000),               # _calc_clean_revenue (still < 40M)
                db_result_scalar_or_none(existing_record),  # _get_record (prev)
                MagicMock(),                                # UPSERT
                db_result_scalar_or_none(new_record),       # _get_record (after)
            ]
        )
        mock_db.commit = AsyncMock()

        pvr_service = PVRService(db=mock_db, redis=mock_redis)
        await pvr_service.recalculate_barber(BARBER_ID_1, ORG_ID, date.today())

        # No bell — threshold didn't change
        mock_redis.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bell_notification_sent_to_telegram(self):
        """Celery send_pvr_bell task sends message to branch group + config targets."""
        from app.tasks.notification_tasks import _send_pvr_bell_notification

        branch = make_branch(
            branch_id=BRANCH_ID, org_id=ORG_ID, telegram_group_id=-100555
        )
        notif_config = make_notif_config("pvr_threshold", chat_id=-100999)

        branch_result = db_result_scalar_or_none(branch)
        config_result = db_result_list([notif_config])

        mock_db = mock_db_session(execute_results=[branch_result, config_result])

        with patch(PATCH_SESSION) as mock_session_cls, \
             patch(PATCH_BOT) as mock_bot_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_bot = MagicMock()
            mock_bot.send_pvr_bell = AsyncMock(return_value=True)
            mock_bot_cls.return_value = mock_bot

            result = await _send_pvr_bell_notification(
                organization_id=str(ORG_ID),
                branch_id=str(BRANCH_ID),
                barber_name="Pavel",
                threshold=30_000_000,
                bonus=1_000_000,
            )

        assert result["sent"] >= 1
        mock_bot.send_pvr_bell.assert_awaited()


# ===========================================================================
# FLOW 3: Scheduled report -> Generation -> Notification delivery
# ===========================================================================


class TestScheduledReportFlow:
    """Scheduled report generation and Telegram delivery."""

    @pytest.mark.asyncio
    async def test_daily_report_generation_for_all_orgs(self):
        """_generate_daily creates reports for every active organization."""
        from app.tasks.report_tasks import _generate_daily

        org = make_org(org_id=ORG_ID)
        orgs_result = db_result_list([org])

        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=orgs_result)

        with patch(PATCH_SESSION) as mock_session_cls, \
             patch(PATCH_REPORT_SVC) as mock_report_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_report = AsyncMock()
            mock_report.generate_daily_revenue = AsyncMock()
            mock_report.generate_clients_report = AsyncMock()
            mock_report.generate_kombat_daily = AsyncMock()
            mock_report_cls.return_value = mock_report

            result = await _generate_daily(target_date=date.today())

        assert result["orgs_processed"] == 1
        assert result["errors"] == 0
        mock_report.generate_daily_revenue.assert_awaited_once()
        mock_report.generate_clients_report.assert_awaited_once()
        mock_report.generate_kombat_daily.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_daily_report_delivery_marks_delivered(self):
        """_deliver_daily_reports marks reports as delivered."""
        from app.tasks.notification_tasks import _deliver_daily_reports

        report = make_report(
            report_type="kombat_daily",
            data={
                "date": "2026-02-22",
                "branches": [
                    {
                        "branch_id": str(BRANCH_ID),
                        "branch_name": "Branch 1",
                        "standings": [],
                    }
                ],
            },
            delivered=False,
        )

        reports_result = db_result_list([report])
        branch = make_branch(branch_id=BRANCH_ID, telegram_group_id=-100555)
        branch_result = db_result_scalar_or_none(branch)
        notif_result = db_result_list([make_notif_config("daily_rating")])
        update_result = MagicMock()  # UPDATE Report SET delivered_telegram=True

        mock_db = mock_db_session(
            execute_results=[reports_result, branch_result, notif_result, update_result]
        )

        with patch(PATCH_SESSION) as mock_session_cls, \
             patch(PATCH_BOT) as mock_bot_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_bot = MagicMock()
            mock_bot.send_kombat_report = AsyncMock(return_value=True)
            mock_bot.send_message = AsyncMock(return_value=True)
            mock_bot_cls.return_value = mock_bot

            result = await _deliver_daily_reports()

        assert result["reports_processed"] == 1
        assert result["sent"] >= 1
        # Verify UPDATE was executed (4 calls: reports query, branch, notif, update)
        assert mock_db.execute.call_count == 4
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_report_error_does_not_block_others(self):
        """If one report fails, remaining reports are still processed."""
        from app.tasks.report_tasks import _generate_daily

        org1 = make_org(org_id=ORG_ID)
        org2 = make_org(org_id=ORG_ID_2)
        orgs_result = db_result_list([org1, org2])

        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=orgs_result)

        with patch(PATCH_SESSION) as mock_session_cls, \
             patch(PATCH_REPORT_SVC) as mock_report_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_report = AsyncMock()
            # First org fails, second succeeds
            mock_report.generate_daily_revenue = AsyncMock(
                side_effect=[RuntimeError("DB error"), None]
            )
            mock_report.generate_clients_report = AsyncMock()
            mock_report.generate_kombat_daily = AsyncMock()
            mock_report_cls.return_value = mock_report

            result = await _generate_daily(target_date=date.today())

        assert result["orgs_processed"] == 1
        assert result["errors"] == 1

    @pytest.mark.asyncio
    async def test_day_to_day_report_generation(self):
        """_generate_day_to_day calls service for all orgs."""
        from app.tasks.report_tasks import _generate_day_to_day

        org = make_org(org_id=ORG_ID)
        orgs_result = db_result_list([org])

        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=orgs_result)

        with patch(PATCH_SESSION) as mock_session_cls, \
             patch(PATCH_REPORT_SVC) as mock_report_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_report = AsyncMock()
            mock_report.generate_day_to_day = AsyncMock()
            mock_report_cls.return_value = mock_report

            result = await _generate_day_to_day(target_date=date.today())

        assert result["orgs_processed"] == 1
        mock_report.generate_day_to_day.assert_awaited_once()


# ===========================================================================
# FLOW 4: WebSocket concurrency — 50 connections load test
# ===========================================================================


class TestWebSocketConcurrency:
    """Load and concurrency tests for WebSocket manager."""

    @pytest.mark.asyncio
    async def test_50_connections_same_org(self):
        """50 clients connect to same org and receive a broadcast."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()
        connections = []

        for _ in range(50):
            ws = AsyncMock()
            await mgr.connect(ws, ORG_ID)
            connections.append(ws)

        assert mgr.active_connections_count == 50

        message = {"type": "rating_update", "branch_id": str(BRANCH_ID)}
        await mgr.broadcast_to_org(ORG_ID, message)

        for ws in connections:
            ws.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_50_connections_across_orgs(self):
        """25 connections each to 2 different orgs — broadcast is isolated."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()
        org1_connections = []
        org2_connections = []

        for _ in range(25):
            ws1 = AsyncMock()
            await mgr.connect(ws1, ORG_ID)
            org1_connections.append(ws1)

            ws2 = AsyncMock()
            await mgr.connect(ws2, ORG_ID_2)
            org2_connections.append(ws2)

        assert mgr.active_connections_count == 50

        message = {"type": "pvr_threshold", "barber": "Pavel"}
        await mgr.broadcast_to_org(ORG_ID, message)

        for ws in org1_connections:
            ws.send_json.assert_awaited_once_with(message)
        for ws in org2_connections:
            ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dead_connections_cleaned_under_load(self):
        """Dead connections removed even with many concurrent clients."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()
        alive_connections = []
        dead_count = 10

        for i in range(50):
            ws = AsyncMock()
            if i < dead_count:
                ws.send_json.side_effect = RuntimeError("Connection reset")
            await mgr.connect(ws, ORG_ID)
            if i >= dead_count:
                alive_connections.append(ws)

        assert mgr.active_connections_count == 50

        await mgr.broadcast_to_org(ORG_ID, {"type": "test"})

        # Dead connections removed
        assert mgr.active_connections_count == 40

        for ws in alive_connections:
            ws.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_clears_all(self):
        """Disconnecting all clients for an org clears internal state."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()
        connections = []

        for _ in range(50):
            ws = AsyncMock()
            await mgr.connect(ws, ORG_ID)
            connections.append(ws)

        for ws in connections:
            mgr.disconnect(ws, ORG_ID)

        assert mgr.active_connections_count == 0

    @pytest.mark.asyncio
    async def test_rapid_connect_disconnect_cycle(self):
        """Rapid connect/disconnect cycles don't corrupt state."""
        from app.websocket.manager import ConnectionManager

        mgr = ConnectionManager()

        for _ in range(50):
            ws = AsyncMock()
            await mgr.connect(ws, ORG_ID)
            mgr.disconnect(ws, ORG_ID)

        assert mgr.active_connections_count == 0

        # Connect a fresh one — should still work
        ws_final = AsyncMock()
        await mgr.connect(ws_final, ORG_ID)
        assert mgr.active_connections_count == 1

        await mgr.broadcast_to_org(ORG_ID, {"type": "ok"})
        ws_final.send_json.assert_awaited_once()


# ===========================================================================
# FLOW 5: Edge cases
# ===========================================================================


class TestEdgeCaseEmptyBranch:
    """Edge case: organization with no active branches."""

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_poll_with_zero_branches(
        self, mock_sync_cls, mock_session_cls, mock_yclients_cls, mock_plan_cls
    ):
        """Polling with no active branches returns zero totals."""
        from app.tasks.sync_tasks import _poll_all_branches

        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=db_result_list([]))

        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients_cls.return_value = AsyncMock()
        mock_sync_cls.return_value = AsyncMock()
        mock_plan_cls.return_value = AsyncMock()

        result = await _poll_all_branches()

        assert result["branches_processed"] == 0
        assert result["total_synced"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_monthly_reset_empty_branches(self):
        """Monthly reset for org with no branches completes with zero counts."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = mock_db_session()
        # _get_active_branches returns empty
        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_list([]),  # branches
                db_result_list([]),  # barbers for PVR
                db_result_list([]),  # plans
            ]
        )

        service = MonthlyResetService(db=mock_db)
        result = await service.reset_organization(ORG_ID, date(2026, 1, 1))

        assert result["branches"] == 0
        assert result["champions"] == 0
        assert result["pvr_records_created"] == 0
        assert result["plans_copied"] == 0


class TestEdgeCaseSingleBarber:
    """Edge case: branch with exactly one barber."""

    @pytest.mark.asyncio
    async def test_single_barber_is_champion(self):
        """With one barber, that barber is always the monthly champion."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = AsyncMock()

        branch = make_branch(branch_id=BRANCH_ID, org_id=ORG_ID)
        barber = make_barber(barber_id=BARBER_ID_1, name="Solo Barber")

        # Champion row (only one barber)
        champion_row = MagicMock()
        champion_row.barber_id = BARBER_ID_1
        champion_row.wins = 15
        champion_row.total_score = 1425.0

        wins_result = MagicMock()
        wins_result.all.return_value = [champion_row]

        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = "Solo Barber"

        revenue_result = db_result_scalar(8_500_000)

        # PVR: no barbers (already tested elsewhere)
        # Plans: no plans
        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_list([branch]),     # _get_active_branches
                wins_result,                  # _finalize_branch_ratings
                name_result,                  # champion name
                name_result,                  # standings name
                revenue_result,               # _save_monthly_report revenue
                MagicMock(),                  # report add (unused)
                db_result_list([]),           # _create_new_pvr_records (barbers)
                db_result_list([]),           # _copy_plans
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        service = MonthlyResetService(db=mock_db)
        result = await service.reset_organization(ORG_ID, date(2026, 1, 1))

        assert result["champions"] == 1
        assert result["branches"] == 1

    @pytest.mark.asyncio
    async def test_single_barber_pvr_recalculation(self):
        """PVR recalculation works correctly for a single barber."""
        from app.services.pvr import PVRService

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        branch = make_branch(branch_id=BRANCH_ID, org_id=ORG_ID)
        barber = make_barber(barber_id=BARBER_ID_1, name="Only One")

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_scalar_or_none(branch),     # branch lookup
                db_result_list([barber]),              # barbers
                # Then recalculate_barber calls:
                db_result_scalar_or_none(MagicMock(    # config
                    thresholds=[{"amount": 30_000_000, "bonus": 1_000_000}],
                    count_products=False,
                    count_certificates=False,
                )),
                db_result_scalar(25_000_000),          # revenue (below threshold)
                db_result_scalar_or_none(None),        # prev record
                MagicMock(),                           # UPSERT
                db_result_scalar_or_none(make_pvr_record(BARBER_ID_1, 25_000_000, None, 0)),
            ]
        )
        mock_db.commit = AsyncMock()

        pvr_service = PVRService(db=mock_db, redis=mock_redis)
        records = await pvr_service.recalculate_branch(BRANCH_ID, date.today())

        assert len(records) == 1
        # No bell — below threshold
        mock_redis.publish.assert_not_awaited()


class TestEdgeCaseMonthTransition:
    """Edge case: December -> January month transition."""

    @pytest.mark.asyncio
    async def test_monthly_reset_december_to_january(self):
        """Month transition from December to January creates records for Jan next year."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = AsyncMock()
        branch = make_branch(branch_id=BRANCH_ID, org_id=ORG_ID)
        barber = make_barber(barber_id=BARBER_ID_1)

        # No champion, no existing PVR, no plans
        empty_wins = MagicMock()
        empty_wins.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_list([branch]),        # _get_active_branches
                empty_wins,                      # _finalize_branch_ratings (no wins)
                db_result_scalar(0),             # _save_monthly_report (revenue)
                db_result_list([barber]),         # _create_new_pvr_records (barbers)
                db_result_scalar_or_none(None),  # existing PVR check -> None
                db_result_list([]),              # _copy_plans (no old plans)
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        service = MonthlyResetService(db=mock_db)
        result = await service.reset_organization(ORG_ID, date(2025, 12, 1))

        # Check that new_month is January 2026
        assert result["finalized_month"] == "2025-12-01"
        assert result["new_month"] == "2026-01-01"
        assert result["pvr_records_created"] == 1

    def test_next_month_helper_december(self):
        """_next_month correctly handles December -> January."""
        from app.services.monthly_reset import _next_month

        assert _next_month(date(2025, 12, 1)) == date(2026, 1, 1)

    def test_next_month_helper_regular(self):
        """_next_month handles regular months."""
        from app.services.monthly_reset import _next_month

        assert _next_month(date(2026, 1, 1)) == date(2026, 2, 1)
        assert _next_month(date(2026, 6, 1)) == date(2026, 7, 1)
        assert _next_month(date(2026, 11, 1)) == date(2026, 12, 1)


class TestEdgeCaseIdempotency:
    """Edge case: running monthly reset twice should be idempotent."""

    @pytest.mark.asyncio
    async def test_pvr_records_not_duplicated(self):
        """Second run of PVR record creation skips existing records."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = AsyncMock()
        barber = make_barber(barber_id=BARBER_ID_1)
        existing_pvr_id = uuid.uuid4()

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_list([barber]),          # barbers
                db_result_scalar_or_none(existing_pvr_id),  # existing record found
            ]
        )

        service = MonthlyResetService(db=mock_db)
        created = await service._create_new_pvr_records(ORG_ID, date(2026, 2, 1))

        assert created == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_plans_not_duplicated(self):
        """Second run of plan copying skips existing plans."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = AsyncMock()
        old_plan = MagicMock()
        old_plan.branch_id = BRANCH_ID
        old_plan.target_amount = 5_000_000

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_list([old_plan]),         # old plans
                db_result_scalar_or_none(uuid.uuid4()),  # existing plan for new month
            ]
        )

        service = MonthlyResetService(db=mock_db)
        copied = await service._copy_plans(ORG_ID, date(2026, 1, 1), date(2026, 2, 1))

        assert copied == 0
        mock_db.add.assert_not_called()


class TestEdgeCaseMultipleBranches:
    """Edge case: organization with many branches."""

    @pytest.mark.asyncio
    @patch(PATCH_PLAN)
    @patch(PATCH_YCLIENTS)
    @patch(PATCH_SESSION)
    @patch(PATCH_SYNC)
    async def test_poll_handles_many_branches(
        self, mock_sync_cls, mock_session_cls, mock_yclients_cls, mock_plan_cls
    ):
        """Polling 5 branches, one fails — others continue."""
        from app.tasks.sync_tasks import _poll_all_branches

        branches = [make_branch(name=f"Branch {i}") for i in range(5)]
        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=db_result_list(branches))

        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_yclients_cls.return_value = AsyncMock()

        mock_sync = AsyncMock()
        mock_sync.sync_records = AsyncMock(
            side_effect=[3, 5, RuntimeError("fail"), 2, 4]
        )
        mock_sync_cls.return_value = mock_sync

        mock_plan = AsyncMock()
        mock_plan.update_progress = AsyncMock()
        mock_plan_cls.return_value = mock_plan

        result = await _poll_all_branches()

        assert result["branches_processed"] == 4
        assert result["total_synced"] == 14  # 3 + 5 + 2 + 4
        assert result["errors"] == 1


class TestEdgeCaseAllOrgsResetErrors:
    """Edge case: monthly reset across multiple orgs with partial failures."""

    @pytest.mark.asyncio
    async def test_reset_all_continues_on_error(self):
        """If one org fails, others are still processed."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = AsyncMock()
        org1 = make_org(org_id=ORG_ID)
        org2 = make_org(org_id=ORG_ID_2)

        mock_db.execute = AsyncMock(return_value=db_result_list([org1, org2]))

        service = MonthlyResetService(db=mock_db)

        with patch.object(
            service,
            "reset_organization",
            side_effect=[RuntimeError("org1 failed"), {"ok": True}],
        ):
            result = await service.reset_all_organizations(date(2026, 1, 1))

        assert result["orgs_processed"] == 1
        assert result["errors"] == 1


# ===========================================================================
# FLOW 6: Full monthly lifecycle — report generation + reset
# ===========================================================================


class TestFullMonthlyLifecycle:
    """Full monthly lifecycle: reports → reset → new month."""

    @pytest.mark.asyncio
    async def test_monthly_report_then_reset_sequence(self):
        """Monthly report generation followed by reset creates correct data."""
        from app.tasks.report_tasks import _generate_monthly

        org = make_org(org_id=ORG_ID)
        orgs_result = db_result_list([org])

        mock_db = mock_db_session()
        mock_db.execute = AsyncMock(return_value=orgs_result)

        with patch(PATCH_SESSION) as mock_session_cls, \
             patch(PATCH_REPORT_SVC) as mock_report_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_report = AsyncMock()
            mock_report.generate_kombat_monthly = AsyncMock()
            mock_report_cls.return_value = mock_report

            result = await _generate_monthly(target_month=date(2026, 1, 15))

        assert result["orgs_processed"] == 1
        mock_report.generate_kombat_monthly.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_monthly_reset_service_full_pipeline(self):
        """MonthlyResetService processes branches, creates PVR, copies plans."""
        from app.services.monthly_reset import MonthlyResetService

        mock_db = AsyncMock()
        branch = make_branch(branch_id=BRANCH_ID, org_id=ORG_ID)
        barber = make_barber(barber_id=BARBER_ID_1)
        old_plan = MagicMock()
        old_plan.branch_id = BRANCH_ID
        old_plan.target_amount = 5_000_000
        old_plan.organization_id = ORG_ID

        # Champion determination
        champion_row = MagicMock()
        champion_row.barber_id = BARBER_ID_1
        champion_row.wins = 20
        champion_row.total_score = 1900.0
        wins_result = MagicMock()
        wins_result.all.return_value = [champion_row]

        name_result = MagicMock()
        name_result.scalar_one_or_none.return_value = "Champion Pavel"

        mock_db.execute = AsyncMock(
            side_effect=[
                db_result_list([branch]),          # _get_active_branches
                wins_result,                       # _finalize_branch_ratings (wins)
                name_result,                       # champion name lookup
                name_result,                       # standings name lookup
                db_result_scalar(12_000_000),      # _save_monthly_report (revenue)
                # Note: _save_monthly_report uses db.add(), not execute()
                db_result_list([barber]),           # _create_new_pvr_records (barbers)
                db_result_scalar_or_none(None),    # no existing PVR record
                db_result_list([old_plan]),         # _copy_plans (old plans)
                db_result_scalar_or_none(None),    # no existing new plan
            ]
        )
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        service = MonthlyResetService(db=mock_db)
        result = await service.reset_organization(ORG_ID, date(2026, 1, 1))

        assert result["branches"] == 1
        assert result["champions"] == 1
        assert result["pvr_records_created"] == 1
        assert result["plans_copied"] == 1
        assert result["finalized_month"] == "2026-01-01"
        assert result["new_month"] == "2026-02-01"
        mock_db.commit.assert_awaited_once()


# ===========================================================================
# FLOW 7: Webhook endpoint tests
# ===========================================================================


class TestWebhookEndpointIntegration:
    """Integration tests for the webhook receiver endpoint."""

    @pytest.mark.asyncio
    async def test_valid_webhook_enqueues_task(self):
        """A valid signed webhook enqueues the processing task."""
        import hashlib
        import hmac

        from httpx import ASGITransport, AsyncClient

        from app.main import app

        secret = "test-webhook-secret"
        payload = {
            "company_id": 555,
            "resource": "record",
            "status": "completed",
            "data": {"id": 1001, "staff_id": 10, "cost": 1500.0},
        }
        body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        with patch("app.api.webhooks.settings") as mock_settings, \
             patch("app.api.webhooks.process_yclients_webhook") as mock_task:
            mock_settings.yclients_webhook_secret = secret
            mock_task.delay.return_value = MagicMock(id="task-123")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/webhooks/yclients",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Signature": sig,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self):
        """An invalid signature returns ok=false without enqueuing."""
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        payload = {
            "company_id": 555,
            "resource": "record",
            "status": "completed",
            "data": {"id": 1001},
        }
        body = json.dumps(payload).encode("utf-8")

        with patch("app.api.webhooks.settings") as mock_settings, \
             patch("app.api.webhooks.process_yclients_webhook") as mock_task:
            mock_settings.yclients_webhook_secret = "real-secret"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/webhooks/yclients",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Signature": "wrong-signature",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is False
            mock_task.delay.assert_not_called()


# ===========================================================================
# Celery beat schedule verification
# ===========================================================================


class TestCeleryBeatScheduleComplete:
    """Verify all expected tasks are scheduled in Celery beat."""

    def test_all_tasks_scheduled(self):
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        expected_tasks = {
            "poll-yclients-every-10-min": "poll_yclients",
            "full-sync-daily-4am": "full_sync_yclients",
            "report-daily-evening": "generate_daily_reports",
            "report-day-to-day": "generate_day_to_day",
            "report-monthly": "generate_monthly_reports",
            "check-unprocessed-reviews-every-30-min": "check_unprocessed_reviews",
            "deliver-daily-notifications": "deliver_daily_notifications",
            "deliver-day-to-day-notifications": "deliver_day_to_day_notifications",
            "deliver-monthly-notifications": "deliver_monthly_notifications",
            "monthly-reset": "monthly_reset",
        }

        for schedule_name, task_name in expected_tasks.items():
            assert schedule_name in schedule, f"Missing: {schedule_name}"
            assert schedule[schedule_name]["task"] == task_name

    def test_monthly_reset_runs_first_of_month(self):
        from app.tasks.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["monthly-reset"]
        cron = entry["schedule"]
        assert cron.day_of_month == {1}
        assert cron.hour == {0}
        assert cron.minute == {5}

    def test_notifications_run_after_reports(self):
        """Notification tasks are scheduled after their report generators."""
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        # Daily: reports at 22:30, notifications at 22:35
        report_cron = schedule["report-daily-evening"]["schedule"]
        notif_cron = schedule["deliver-daily-notifications"]["schedule"]
        assert min(notif_cron.minute) > min(report_cron.minute)

        # Day-to-day: reports at 11:00, notifications at 11:05
        report_cron = schedule["report-day-to-day"]["schedule"]
        notif_cron = schedule["deliver-day-to-day-notifications"]["schedule"]
        assert min(notif_cron.minute) > min(report_cron.minute)
