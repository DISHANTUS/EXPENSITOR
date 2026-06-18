"""Async database engine, session factory, and FastAPI session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Managed Postgres (Neon) requires TLS; pass it via asyncpg connect_args since the
# asyncpg dialect ignores libpq's `sslmode=`. Empty locally (DB_SSL off).
_connect_args = {"ssl": True} if settings.DB_SSL else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the lifetime of a request."""
    async with AsyncSessionLocal() as session:
        yield session
