"""Seed baseline exchange rates (USD-anchored) so the currency converter and
income FX-conversion work offline.

These are STATIC PLACEHOLDER values, to be superseded by a live Frankfurter
fetch in a later phase. Stored as ``base=USD, quote=X`` rows; cross-rates
(e.g. JPY->INR) are derived by the currency service.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExchangeRate

# Fixed snapshot date; live rates added later will have newer dates and win.
SEED_RATE_DATE = date(2026, 6, 1)

# 1 USD = <value> of each currency (illustrative).
USD_ANCHORED_RATES: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "INR": Decimal("83.20"),
    "JPY": Decimal("141.00"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "CZK": Decimal("23.00"),
}


async def seed_exchange_rates(session: AsyncSession) -> int:
    rows = [
        {
            "base_currency": "USD",
            "quote_currency": code,
            "rate": rate,
            "rate_date": SEED_RATE_DATE,
            "source": "seed",
        }
        for code, rate in USD_ANCHORED_RATES.items()
    ]
    stmt = pg_insert(ExchangeRate).values(rows).on_conflict_do_nothing(
        index_elements=["base_currency", "quote_currency", "rate_date"]
    )
    await session.execute(stmt)
    return len(rows)
