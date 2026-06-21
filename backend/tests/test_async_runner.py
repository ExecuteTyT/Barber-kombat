"""Regression tests for the Celery shared event-loop runner.

These guard the fix for the asyncpg/redis "bound to a different loop" /
"another operation is in progress" failures that broke every scheduled task
after the first one per worker process.
"""

import asyncio

from app.tasks._async import run_async


def test_run_async_returns_result():
    async def f() -> int:
        return 42

    assert run_async(f()) == 42


def test_run_async_reuses_one_loop():
    """asyncio.run() would create a fresh loop each call; run_async must not."""
    loops: list[asyncio.AbstractEventLoop] = []

    async def grab() -> None:
        loops.append(asyncio.get_running_loop())

    run_async(grab())
    run_async(grab())

    assert loops[0] is loops[1]


def test_loop_bound_future_survives_across_calls():
    """A Future created on the first call's loop must be awaitable on the next.

    Under asyncio.run() the second call runs on a different loop and awaiting
    the Future raises 'got Future attached to a different loop' — exactly the
    class of error that broke the shared DB engine / Redis client.
    """

    async def _create_pending_future() -> asyncio.Future:
        return asyncio.get_running_loop().create_future()

    fut = run_async(_create_pending_future())

    async def resolve_and_await() -> str:
        asyncio.get_running_loop().call_soon(fut.set_result, "ok")
        return await fut

    assert run_async(resolve_and_await()) == "ok"
