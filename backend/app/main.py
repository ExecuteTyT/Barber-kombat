import asyncio
import contextlib
import json
import uuid
from contextlib import asynccontextmanager

import jwt as pyjwt
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.config import router as config_router
from app.api.kombat import router as kombat_router
from app.api.plans import router as plans_router
from app.api.pvr import router as pvr_router
from app.api.reports import router as reports_router
from app.api.reviews import router as reviews_router
from app.api.webhooks import router as webhooks_router
from app.auth.jwt import decode_access_token
from app.config import settings
from app.database import engine
from app.logging import setup_logging
from app.redis import redis_client
from app.websocket import ws_manager

logger = structlog.stdlib.get_logger()


async def _ws_redis_listener() -> None:
    """Subscribe to ws:org:* Redis channels and broadcast to WebSocket clients.

    Runs as a background asyncio task during the application lifespan.
    When a Celery worker (or any process) publishes a message to a
    ``ws:org:{organization_id}`` channel, this listener picks it up
    and forwards it to all WebSocket clients in that organization.
    """
    sub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = sub_redis.pubsub()
    await pubsub.psubscribe("ws:org:*")

    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel: str = message["channel"]  # "ws:org:{uuid}"
                try:
                    org_id = uuid.UUID(channel.rsplit(":", 1)[-1])
                    data = json.loads(message["data"])
                    await ws_manager.broadcast_to_org(org_id, data)
                except Exception:
                    await logger.aexception(
                        "Error processing WS pubsub message",
                        channel=channel,
                    )
    finally:
        await pubsub.punsubscribe("ws:org:*")
        await sub_redis.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    setup_logging()
    await logger.ainfo("Starting Barber Kombat API", env=settings.app_env)

    # Start WebSocket Redis Pub/Sub listener
    listener_task = asyncio.create_task(_ws_redis_listener())

    yield

    # Shutdown
    listener_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await listener_task
    await redis_client.aclose()
    await engine.dispose()
    await logger.ainfo("Shutting down Barber Kombat API")


app = FastAPI(
    title="Barber Kombat API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
    openapi_url="/api/openapi.json" if settings.is_development else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3005",
        settings.telegram_mini_app_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(kombat_router, prefix="/api/v1")
app.include_router(plans_router, prefix="/api/v1")
app.include_router(pvr_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


# --- WebSocket endpoint ---


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    """WebSocket endpoint for real-time updates.

    Clients connect with ``ws://host/ws?token=JWT``.  The JWT is validated
    and the client is registered under its ``organization_id``.  The server
    then pushes events (rating updates, PVR thresholds, etc.) scoped to
    that organization.

    Keepalive: send ``"ping"`` text to receive ``"pong"``.
    """
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_access_token(token)
    except pyjwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    org_id = payload.organization_id
    await ws_manager.connect(websocket, org_id)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, org_id)
        await logger.ainfo(
            "WebSocket disconnected",
            org_id=str(org_id),
            total=ws_manager.active_connections_count,
        )


# --- Health check ---


@app.get("/api/health")
async def health_check():
    """Health check endpoint that verifies DB and Redis connections."""
    result = {"status": "ok", "db": "disconnected", "redis": "disconnected"}

    # Check PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        result["db"] = "connected"
    except Exception:
        result["status"] = "degraded"

    # Check Redis
    try:
        await redis_client.ping()
        result["redis"] = "connected"
    except Exception:
        result["status"] = "degraded"

    return result
