"""Learned daily habits — "is the ₹200 for travel over?" (compact-Home confirm).

Distinct from RecurringRule (user-declared monthly subscriptions/EMIs with a
fixed recurrence_day): this LEARNS unstated day-to-day habits purely from
expense history, so the companion can offer a one-tap confirmation instead of
making the user type the same amount every day.

Weekday and weekend are modelled separately — a commute happens Mon–Fri and a
weekend looks nothing like it, so mixing them would both hide real weekday
habits and invent phantom weekend ones.

Deliberately conservative: it only predicts what the user has actually,
repeatedly done, and it never writes anything. Confirming is a normal
POST /expenses from the client (the user's tap is the only thing that creates
money data) — so a wrong prediction costs one ignored card, never a bad row.
"""

from __future__ import annotations

import statistics
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense
from app.services import category_service

_LOOKBACK_DAYS = 28              # ~4 weeks: enough for 8 weekend days / 20 weekday days
_MIN_HISTORY_DAYS = 14           # the user's "after 2 weeks of learning" gate
_MIN_OCCURRENCES = 4             # never predict off one or two coincidences
_MIN_OCCURRENCE_RATE = 0.6       # must happen on most matching days to count as a habit
_MAX_SPREAD = Decimal("0.35")    # amounts must be reasonably consistent (rel. deviation)


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


async def has_min_history(db: AsyncSession, user_id: uuid.UUID, today: date) -> bool:
    earliest = await db.scalar(
        select(func.min(Expense.expense_date)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None))
    )
    return earliest is not None and (today - earliest).days >= _MIN_HISTORY_DAYS


def _relative_spread(amounts: list[Decimal]) -> Decimal:
    """Mean absolute deviation from the median, relative to the median — a
    cheap consistency measure that (unlike stdev) isn't wrecked by one outlier."""
    med = statistics.median(amounts)
    if med == 0:
        return Decimal("1")
    spread = sum(abs(a - med) for a in amounts) / len(amounts)
    return Decimal(spread) / Decimal(med)


async def predict_today(
    db: AsyncSession, user_id: uuid.UUID, *, today: date
) -> list[dict]:
    """Habits that match today's day-type and haven't been logged yet today."""
    if not await has_min_history(db, user_id, today):
        return []

    start = today - timedelta(days=_LOOKBACK_DAYS)
    rows = (await db.execute(
        select(Expense.category_id, Expense.expense_date,
               func.sum(Expense.converted_amount).label("amount"))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None),
               Expense.expense_date >= start, Expense.expense_date < today,
               Expense.category_id.is_not(None))
        .group_by(Expense.category_id, Expense.expense_date)
    )).all()
    if not rows:
        return []

    weekend_today = _is_weekend(today)
    # How many candidate days of today's type are actually in the window —
    # the denominator for "happens on most days".
    eligible_days = sum(
        1 for i in range(1, _LOOKBACK_DAYS + 1)
        if _is_weekend(today - timedelta(days=i)) == weekend_today
    )
    if eligible_days == 0:
        return []

    by_category: dict[uuid.UUID, list[Decimal]] = {}
    for category_id, day, amount in rows:
        if _is_weekend(day) != weekend_today:
            continue
        by_category.setdefault(category_id, []).append(Decimal(amount))

    already_logged = {
        r[0] for r in (await db.execute(
            select(Expense.category_id).where(
                Expense.user_id == user_id, Expense.deleted_at.is_(None),
                Expense.expense_date == today)
        )).all()
    }

    name_map = {c.id: c.name for c in await category_service.list_for_user(db, user_id)}
    out: list[dict] = []
    for category_id, amounts in by_category.items():
        if category_id in already_logged or len(amounts) < _MIN_OCCURRENCES:
            continue
        rate = len(amounts) / eligible_days
        if rate < _MIN_OCCURRENCE_RATE:
            continue
        spread = _relative_spread(amounts)
        if spread > _MAX_SPREAD:
            continue                       # too erratic to be worth pre-filling
        out.append({
            "category_id": str(category_id),
            "label": name_map.get(category_id, "that category"),
            "amount": float(statistics.median(amounts)),
            "occurrences": len(amounts),
            "day_type": "weekend" if weekend_today else "weekday",
            "confidence": "high" if rate >= 0.85 and spread <= Decimal("0.15") else "medium",
        })
    out.sort(key=lambda p: p["amount"], reverse=True)
    return out
