"""Tests for WebSocket connection manager, endpoint, and rating publish."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.main import app
from app.websocket.manager import ConnectionManager

# --- Test constants ---

ORG_ID = uuid.uuid4()
ORG_ID_2 = uuid.uuid4()
USER_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()


# --- Helpers ---


def make_mock_ws() -> AsyncMock:
    """Create a mock WebSocket object."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def make_valid_token(
    user_id: uuid.UUID = USER_ID,
    org_id: uuid.UUID = ORG_ID,
    role: str = "barber",
) -> str:
    """Create a valid JWT token for testing."""
    return create_access_token(user_id, org_id, role)


# --- Tests: ConnectionManager ---


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_registers_websocket(self):
        """After connect, connection count increases."""
        mgr = ConnectionManager()
        ws = make_mock_ws()

        await mgr.connect(ws, ORG_ID)

        assert mgr.active_connections_count == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_websocket(self):
        """After disconnect, connection count returns to 0."""
        mgr = ConnectionManager()
        ws = make_mock_ws()

        await mgr.connect(ws, ORG_ID)
        mgr.disconnect(ws, ORG_ID)

        assert mgr.active_connections_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_in_org(self):
        """Broadcast sends to all connections in the same org."""
        mgr = ConnectionManager()
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()

        await mgr.connect(ws1, ORG_ID)
        await mgr.connect(ws2, ORG_ID)

        message = {"type": "rating_update", "data": "test"}
        await mgr.broadcast_to_org(ORG_ID, message)

        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_only_to_target_org(self):
        """Broadcast to one org doesn't affect another org's connections."""
        mgr = ConnectionManager()
        ws_org1 = make_mock_ws()
        ws_org2 = make_mock_ws()

        await mgr.connect(ws_org1, ORG_ID)
        await mgr.connect(ws_org2, ORG_ID_2)

        message = {"type": "test"}
        await mgr.broadcast_to_org(ORG_ID, message)

        ws_org1.send_json.assert_awaited_once_with(message)
        ws_org2.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        """Connections that raise on send are removed."""
        mgr = ConnectionManager()
        ws_alive = make_mock_ws()
        ws_dead = make_mock_ws()
        ws_dead.send_json.side_effect = RuntimeError("Connection closed")

        await mgr.connect(ws_alive, ORG_ID)
        await mgr.connect(ws_dead, ORG_ID)
        assert mgr.active_connections_count == 2

        await mgr.broadcast_to_org(ORG_ID, {"type": "test"})

        # Dead ws removed, alive stays
        assert mgr.active_connections_count == 1
        ws_alive.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_no_error(self):
        """Disconnecting an unknown ws doesn't crash."""
        mgr = ConnectionManager()
        ws = make_mock_ws()

        # Should not raise
        mgr.disconnect(ws, ORG_ID)
        assert mgr.active_connections_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_org_no_error(self):
        """Broadcasting to an org with no connections is a no-op."""
        mgr = ConnectionManager()
        await mgr.broadcast_to_org(ORG_ID, {"type": "test"})
        # No error raised

    @pytest.mark.asyncio
    async def test_multiple_orgs_tracked_independently(self):
        """Connections from different orgs are tracked independently."""
        mgr = ConnectionManager()
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()

        await mgr.connect(ws1, ORG_ID)
        await mgr.connect(ws2, ORG_ID_2)

        assert mgr.active_connections_count == 2

        mgr.disconnect(ws1, ORG_ID)
        assert mgr.active_connections_count == 1


# --- Tests: WebSocket Endpoint ---


class TestWebSocketEndpoint:
    @patch("app.main._ws_redis_listener", new_callable=AsyncMock)
    def test_connect_with_valid_token(self, _mock_listener):
        """Valid JWT allows connection, ping/pong works."""
        token = make_valid_token()
        client = TestClient(app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            assert data == "pong"

    @patch("app.main._ws_redis_listener", new_callable=AsyncMock)
    def test_connect_without_token_rejected(self, _mock_listener):
        """Missing token closes connection."""
        client = TestClient(app)
        rejected = False
        try:
            with client.websocket_connect("/ws") as _ws:
                pass
        except Exception:
            rejected = True
        assert rejected, "Connection without token should be rejected"

    @patch("app.main._ws_redis_listener", new_callable=AsyncMock)
    def test_connect_with_invalid_token_rejected(self, _mock_listener):
        """Invalid JWT closes connection."""
        client = TestClient(app)
        rejected = False
        try:
            with client.websocket_connect("/ws?token=bad.jwt.token") as _ws:
                pass
        except Exception:
            rejected = True
        assert rejected, "Connection with invalid token should be rejected"

    @patch("app.main._ws_redis_listener", new_callable=AsyncMock)
    def test_ping_pong_keepalive(self, _mock_listener):
        """Multiple ping/pong exchanges work."""
        token = make_valid_token()
        client = TestClient(app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            for _ in range(3):
                ws.send_text("ping")
                assert ws.receive_text() == "pong"

    @patch("app.main._ws_redis_listener", new_callable=AsyncMock)
    def test_non_ping_message_ignored(self, _mock_listener):
        """Messages other than 'ping' don't produce a response."""
        token = make_valid_token()
        client = TestClient(app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.send_text("hello")
            # Send a ping to verify connection is still alive
            ws.send_text("ping")
            data = ws.receive_text()
            assert data == "pong"


# --- Tests: Rating Engine Redis Publish ---


class TestRatingPublish:
    @pytest.mark.asyncio
    async def test_recalculate_publishes_to_redis(self):
        """After recalculate, redis.publish is called with correct channel."""
        from app.services.rating import RatingEngine

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.publish = AsyncMock()

        branch = MagicMock()
        branch.id = BRANCH_ID
        branch.organization_id = ORG_ID

        barber = MagicMock()
        barber.id = uuid.uuid4()
        barber.name = "Pavel"
        barber.haircut_price = 160000
        barber.role = "barber"
        barber.is_active = True
        barber.branch_id = BRANCH_ID

        visit = MagicMock()
        visit.barber_id = barber.id
        visit.revenue = 1350000
        visit.services_revenue = 250000
        visit.products_count = 0
        visit.extras_count = 2
        visit.status = "completed"

        # DB call sequence for recalculate:
        # 1. branch, 2. config, 3. barbers, 4. visits, 5. reviews
        branch_result = MagicMock()
        branch_result.scalar_one_or_none.return_value = branch

        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None

        barbers_result = MagicMock()
        barbers_scalars = MagicMock()
        barbers_scalars.all.return_value = [barber]
        barbers_result.scalars.return_value = barbers_scalars

        visits_result = MagicMock()
        visits_scalars = MagicMock()
        visits_scalars.all.return_value = [visit]
        visits_result.scalars.return_value = visits_scalars

        reviews_result = MagicMock()
        reviews_result.__iter__ = MagicMock(return_value=iter([]))

        # UPSERT result
        upsert_result = MagicMock()

        # Prize fund calls: config + revenue sum
        config_result2 = MagicMock()
        config_result2.scalar_one_or_none.return_value = None

        revenue_result = MagicMock()
        revenue_result.scalar_one.return_value = 9800000

        mock_db.execute = AsyncMock(
            side_effect=[
                branch_result,
                config_result,
                barbers_result,
                visits_result,
                reviews_result,
                upsert_result,  # UPSERT for 1 barber
                config_result2,
                revenue_result,
            ]
        )
        mock_db.commit = AsyncMock()

        engine = RatingEngine(db=mock_db, redis=mock_redis)
        from datetime import date

        await engine.recalculate(BRANCH_ID, date.today())

        # Verify redis.publish was called
        mock_redis.publish.assert_awaited_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        payload_str = call_args[0][1]

        assert channel == f"ws:org:{ORG_ID}"
        payload = json.loads(payload_str)
        assert payload["type"] == "rating_update"
        assert payload["branch_id"] == str(BRANCH_ID)
        assert len(payload["ratings"]) == 1
        assert payload["ratings"][0]["name"] == "Pavel"
        assert "prize_fund" in payload
