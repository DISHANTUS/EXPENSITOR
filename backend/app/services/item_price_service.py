"""Learn what the user pays for named things, from their confirmed receipts.

Two jobs:
  - record(): store the line items when a receipt is confirmed.
  - typical(): what this user usually pays for a thing — the median of their
    recent observations, robust to one odd buy.

Median, not mean, on purpose: one bulk purchase or one typo shouldn't drag the
"usual" price. And it only speaks once there are a couple of observations —
"you paid ₹58 once" is a fact, not a usual.

Everything here is scoped to one user. A shared/regional price is a separate,
later layer that never reads across users without an explicit privacy decision.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item_price import ItemPrice

# Below this, there's no "usual" yet — just one or two data points.
_MIN_OBSERVATIONS = 2

# How far back "usual" looks. Prices drift; a two-year-old price isn't today's.
_LOOKBACK_DAYS = 365

_MAX_NAME = 200


def name_key(name: str) -> str:
    """Fold to a stable key: lowercase, collapse whitespace. Conservative — it
    never merges different words, only casing/spacing."""
    return re.sub(r"\s+", " ", (name or "").strip().lower())[:_MAX_NAME]


async def record(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    items: list[dict[str, Any]],
    currency: str,
    observed_on: date | None = None,
    merchant: str | None = None,
) -> int:
    """Store confirmed receipt line items as price observations. Returns how
    many were stored. Silently skips anything without a usable name+price —
    a junk line must never become a fake price point."""
    observed_on = observed_on or date.today()
    stored = 0
    for item in items or []:
        raw_name = str(item.get("name") or "").strip()
        key = name_key(raw_name)
        if not key or len(key) < 2:
            continue
        try:
            price = Decimal(str(item.get("price")))
        except (TypeError, ValueError, ArithmeticError):
            continue
        if price <= 0:
            continue
        db.add(ItemPrice(
            user_id=user_id, name=raw_name[:_MAX_NAME], name_key=key,
            price=price, currency=currency.upper(),
            observed_on=observed_on, merchant=(merchant or None),
        ))
        stored += 1
    if stored:
        await db.commit()
    return stored


def _median(values: list[Decimal]) -> Decimal:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


async def typical(
    db: AsyncSession, user_id: uuid.UUID, name: str, *, today: date | None = None
) -> dict[str, Any] | None:
    """What this user usually pays for `name`, or None if there isn't enough
    history to call anything usual yet."""
    today = today or date.today()
    key = name_key(name)
    if not key:
        return None
    since = today - timedelta(days=_LOOKBACK_DAYS)

    rows = await db.execute(
        select(ItemPrice.price, ItemPrice.observed_on, ItemPrice.merchant).where(
            ItemPrice.user_id == user_id,
            ItemPrice.deleted_at.is_(None),
            ItemPrice.name_key == key,
            ItemPrice.observed_on >= since,
        ).order_by(ItemPrice.observed_on.desc())
    )
    observations = list(rows)
    if len(observations) < _MIN_OBSERVATIONS:
        return None

    prices = [Decimal(p) for p, _, _ in observations]
    return {
        "name_key": key,
        "typical_price": str(_median(prices).quantize(Decimal("0.01"))),
        "observations": len(prices),
        "last_price": str(Decimal(observations[0][0]).quantize(Decimal("0.01"))),
        "last_seen": observations[0][1].isoformat(),
    }


async def annotate(
    db: AsyncSession, user_id: uuid.UUID, items: list[dict[str, Any]], *, today: date | None = None
) -> list[dict[str, Any]]:
    """Attach each item's usual price (when known) to a freshly-parsed receipt,
    so the confirm screen can show 'Milk 1L — ₹60 (you usually pay ₹58)'."""
    out: list[dict[str, Any]] = []
    for item in items or []:
        info = await typical(db, user_id, str(item.get("name") or ""), today=today)
        enriched = dict(item)
        if info:
            enriched["typical_price"] = info["typical_price"]
            enriched["observations"] = info["observations"]
        out.append(enriched)
    return out


async def soft_delete_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Used by the reset/clean-slate flow — a user wiping their data must wipe
    their learned prices too."""
    rows = await db.execute(
        select(ItemPrice).where(ItemPrice.user_id == user_id, ItemPrice.deleted_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for row in rows.scalars():
        row.deleted_at = now
    await db.commit()
