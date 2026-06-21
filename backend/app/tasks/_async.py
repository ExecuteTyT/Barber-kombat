"""Shared event-loop runner for Celery tasks.

Celery runs each task synchronously; our task bodies are async. Using
``asyncio.run()`` per task creates and CLOSES a fresh event loop every time,
which breaks the module-level singletons (the SQLAlchemy async engine and the
async Redis client): their connections stay bound to the first (now closed)
loop, so the next task raises
``asyncpg ... cannot perform operation: another operation is in progress`` /
``got Future attached to a different loop`` / ``Event loop is closed``.

``run_async`` keeps ONE persistent loop per worker process (mirroring how the
API runs one loop for many requests), so the shared engine/redis connections
stay valid across tasks.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine on this process's persistent event loop."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)
