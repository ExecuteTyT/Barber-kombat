"""WebSocket connection manager for real-time updates."""

import uuid

import structlog
from fastapi import WebSocket

logger = structlog.stdlib.get_logger()


class ConnectionManager:
    """Manages WebSocket connections grouped by organization_id.

    Each connected client is associated with an organization. Broadcast
    messages are scoped to a single organization so that tenants only
    receive their own events.
    """

    def __init__(self) -> None:
        # organization_id -> set of active WebSocket connections
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}

    async def connect(
        self, websocket: WebSocket, organization_id: uuid.UUID
    ) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self._connections.setdefault(organization_id, set()).add(websocket)
        await logger.ainfo(
            "WebSocket connected",
            org_id=str(organization_id),
            total=self.active_connections_count,
        )

    def disconnect(
        self, websocket: WebSocket, organization_id: uuid.UUID
    ) -> None:
        """Remove a WebSocket connection."""
        conns = self._connections.get(organization_id)
        if conns is not None:
            conns.discard(websocket)
            if not conns:
                del self._connections[organization_id]

    async def broadcast_to_org(
        self, organization_id: uuid.UUID, message: dict
    ) -> None:
        """Send a JSON message to all clients in an organization.

        Dead connections are silently removed.
        """
        conns = self._connections.get(organization_id)
        if not conns:
            return

        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            conns.discard(ws)
            await logger.awarning(
                "Removed dead WebSocket connection",
                org_id=str(organization_id),
            )

    @property
    def active_connections_count(self) -> int:
        """Total number of active WebSocket connections across all orgs."""
        return sum(len(s) for s in self._connections.values())


# Module-level singleton
ws_manager = ConnectionManager()
