"""Live exchange-rate refresh.

Conversions read the latest stored ``ExchangeRate`` rows (see currency_service);
those were only ever seeded once, so rates went stale. This refreshes them from a
free, no-key, USD-anchored public source (open.er-api.com) — fetched on demand
(not a background daemon) and only when the user has opted in and today's rates
aren't already cached. Resilient: a fetch failure never raises and never wipes
the rates we already have.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Currency, ExchangeRate

log = logging.getLogger(__name__)

PROVIDER = "open.er-api.com"
_URL = "https://open.er-api.com/v6/latest/USD"


async def _fetch_usd_rates() -> dict[str, Decimal]:
    """USD-anchored rates from the public provider. Patched out in tests."""
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get(_URL)
        resp.raise_for_status()
        data = resp.json()
    if (data.get("result") or "success") != "success":
        raise ValueError("provider returned a non-success result")
    return {code: Decimal(str(v)) for code, v in (data.get("rates") or {}).items()}


async def _latest_date(db: AsyncSession) -> date | None:
    return await db.scalar(select(func.max(ExchangeRate.rate_date)))


async def status(db: AsyncSession, *, today: date | None = None) -> dict:
    d = await _latest_date(db)
    src = None
    if d is not None:
        src = await db.scalar(
            select(ExchangeRate.source).where(ExchangeRate.rate_date == d).limit(1))
    stale = d is None or (today is not None and d < today)
    return {"rate_date": d, "source": src, "stale": stale}


async def refresh(db: AsyncSession, *, today: date, force: bool = False) -> dict:
    """Upsert USD-anchored rates for ``today``. No-op (no network) when today's
    rates are already cached unless ``force``. Never raises."""
    latest = await _latest_date(db)
    if not force and latest is not None and latest >= today:
        return {"updated": 0, **(await status(db, today=today))}

    codes = set((await db.execute(select(Currency.code))).scalars().all())
    try:
        rates = await _fetch_usd_rates()
    except Exception as exc:  # noqa: BLE001 — a provider hiccup must not break the app
        log.warning("Exchange-rate refresh failed (%s) — keeping cached rates", exc)
        return {"updated": 0, "error": "fetch_failed", **(await status(db, today=today))}

    rows = [
        {"base_currency": "USD", "quote_currency": code, "rate": rates[code],
         "rate_date": today, "source": PROVIDER}
        for code in codes if code in rates
    ]
    if not rows:
        return {"updated": 0, **(await status(db, today=today))}

    stmt = pg_insert(ExchangeRate).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["base_currency", "quote_currency", "rate_date"],
        set_={"rate": stmt.excluded.rate, "source": stmt.excluded.source})
    await db.execute(stmt)
    await db.commit()
    return {"updated": len(rows), "rate_date": today, "source": PROVIDER, "stale": False}
