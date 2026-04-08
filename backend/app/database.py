from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_size=10,
    max_overflow=20,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session


@asynccontextmanager
async def task_sessionmaker():
    """Per-task async sessionmaker for Celery contexts.

    Creates a fresh AsyncEngine with NullPool, yields an async_sessionmaker
    bound to it, and disposes the engine on exit. Required because Celery
    runs each task in a fresh asyncio.run() — sharing the global connection
    pool across event loops causes asyncpg to raise
    `cannot perform operation: another operation is in progress` on the first
    query, because pooled connections stay bound to the previous (now closed)
    event loop.

    Usage:
        async with task_sessionmaker() as Session:
            async with Session() as db:
                ...
    """
    task_engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
    )
    try:
        yield async_sessionmaker(
            task_engine, class_=AsyncSession, expire_on_commit=False
        )
    finally:
        await task_engine.dispose()
