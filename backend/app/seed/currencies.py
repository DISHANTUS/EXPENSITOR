"""Seed the supported currencies. Idempotent (ON CONFLICT DO NOTHING)."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Currency

# Supported currencies. decimal_digits drives rounding/display (JPY has none).
CURRENCIES: list[dict[str, object]] = [
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "decimal_digits": 2},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "decimal_digits": 0},
    {"code": "USD", "name": "US Dollar", "symbol": "$", "decimal_digits": 2},
    {"code": "EUR", "name": "Euro", "symbol": "€", "decimal_digits": 2},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "decimal_digits": 2},
    {"code": "CZK", "name": "Czech Koruna", "symbol": "Kč", "decimal_digits": 2},
]


async def seed_currencies(session: AsyncSession) -> int:
    """Insert any missing currencies. Returns the number of rows attempted."""
    stmt = pg_insert(Currency).values(CURRENCIES).on_conflict_do_nothing(index_elements=["code"])
    await session.execute(stmt)
    return len(CURRENCIES)
