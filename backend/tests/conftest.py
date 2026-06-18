"""Pytest fixtures: a disposable test database + an ASGI client.

Uses a dedicated `<db>_test` database (created if missing), rebuilt fresh for
each test so cases are fully isolated. Currencies are seeded for FK validation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (register all models on Base.metadata)
from app.core.config import settings
from app.core.database import get_db
from app.db.base import Base
from app.main import app
from app.models import Category
from app.seed.categories import seed_categories
from app.seed.currencies import seed_currencies
from app.seed.exchange_rates import seed_exchange_rates

TEST_DB_NAME = f"{settings.POSTGRES_DB}_test"


def _db_url(dbname: str) -> str:
    return (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{dbname}"
    )


async def _ensure_test_database() -> None:
    admin = create_async_engine(_db_url("postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DB_NAME},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        await admin.dispose()


@pytest_asyncio.fixture(autouse=True)
def _ollama_off(monkeypatch):
    """Tests are deterministic regardless of the local .env: never call a live
    Ollama. Narration tests inject a stub `generate` to exercise that path."""
    from app.core.config import settings as _s
    monkeypatch.setattr(_s, "OLLAMA_ENABLED", False)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    await _ensure_test_database()
    eng = create_async_engine(_db_url(TEST_DB_NAME))
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    async with factory() as session:
        await seed_currencies(session)
        await seed_exchange_rates(session)
        await seed_categories(session)
        await session.commit()
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def system_category_id(engine: AsyncEngine) -> str:
    """A seeded system category id, for expense/planned category tests."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        category_id = await session.scalar(
            select(Category.id).where(Category.is_system.is_(True)).limit(1)
        )
    return str(category_id)


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine):
    """A direct AsyncSession on the test DB, for unit-testing services/engine."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
