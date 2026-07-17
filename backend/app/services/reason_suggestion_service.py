"""Learned reason suggestions — so recording a spend is one tap, not a search.

The loop the user described: spend ₹50, and instead of a blank box you get the
reasons you've given before as chips — "chai", "bus", "lunch" — ranked by how
likely each is for *this* spend. Tap one, done. Type a new one and it becomes a
chip next time, automatically. Spend ₹50 for chai every morning and "chai"
floats to the top on its own.

There is no new store for this: the reasons a user has given ARE the
descriptions on their past expenses. So this is derived on read, like everything
else — nothing to migrate, and it starts working the moment someone has any
history at all.

Ranking blends five signals about each past reason:
  - how often they've used it              (frequency)
  - how recently                           (recency, decayed)
  - how close its usual amount is to this   (amount fit)
  - whether they use it on this weekday     (weekday fit)
  - whether it shares this category         (category fit)

Nothing here is invented or model-generated: every chip is a phrase the user
themselves typed before. The most it ever does is re-order their own words.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense

# How far back to learn from. Long enough to catch a monthly rhythm, short
# enough that it reflects who the user is now, not two years ago.
LOOKBACK_DAYS = 120

# A reason needs to have been used at least this many times before it's offered
# as a learned chip. One-offs aren't habits, and offering every single past
# description would bury the useful ones.
_MIN_USES = 2

# Recency half-life: a reason last used this many days ago counts for half of a
# reason used today, all else equal. Keeps stale reasons from crowding fresh ones.
_RECENCY_HALFLIFE_DAYS = 21.0

# Amount is a GATE, not a bonus. A reason whose usual amount is 40x off this
# spend must not win however often it's used — "chai" is not the reason for a
# ₹1900 payment no matter how much chai you drink. So amount multiplies the
# score down toward this floor rather than adding a little on top. The floor is
# non-zero so that with no amount given (or a genuinely new amount) everything
# still ranks on its other merits instead of vanishing.
_AMOUNT_GATE_FLOOR = 0.25

# Weekday / category lift the base a little when they match; they never dominate.
_W_WEEKDAY = 0.5
_W_CATEGORY = 0.6


def _normalise(text: str) -> str:
    """Fold near-duplicates together so "Chai", "chai " and "chai" are one
    reason, while keeping it conservative — we never merge different words."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@dataclass
class _Reason:
    label: str                      # the user's own most-recent casing
    uses: int = 0                   # raw count, for the min-uses gate
    weighted_uses: float = 0.0      # recency-weighted: old uses count for little
    last_used: date | None = None
    amounts: list[Decimal] = field(default_factory=list)
    weekday_hits: int = 0
    category_hits: int = 0


def _amount_fit(amounts: list[Decimal], target: Decimal) -> float:
    """1.0 when this reason's typical amount is right on the spend, decaying as
    it diverges. Relative, so it works the same for ₹50 and ₹5,000."""
    if target <= 0 or not amounts:
        return 0.0
    typical = sorted(amounts)[len(amounts) // 2]  # median: robust to one odd buy
    if typical <= 0:
        return 0.0
    rel = abs(float(typical - target)) / float(target)
    return math.exp(-2.0 * rel)  # ~1 when equal, ~0.14 when double/half


def _recency_fit(last_used: date | None, today: date) -> float:
    if last_used is None:
        return 0.0
    days = max(0, (today - last_used).days)
    return 0.5 ** (days / _RECENCY_HALFLIFE_DAYS)


async def suggest(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    amount: Decimal | None = None,
    on_date: date | None = None,
    category_id: uuid.UUID | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Ranked reasons for a spend, most likely first. Empty when there's no
    history to learn from — in which case the UI just shows a plain box, which
    is the honest thing to do rather than inventing suggestions."""
    on_date = on_date or date.today()
    since = on_date - timedelta(days=LOOKBACK_DAYS)

    rows = await db.execute(
        select(Expense.description, Expense.converted_amount, Expense.expense_date, Expense.category_id).where(
            Expense.user_id == user_id,
            Expense.deleted_at.is_(None),
            Expense.description.is_not(None),
            Expense.expense_date >= since,
            Expense.expense_date <= on_date,
        )
    )

    reasons: dict[str, _Reason] = {}
    for description, amt, day, cat in rows:
        key = _normalise(description or "")
        if not key:
            continue
        r = reasons.get(key)
        if r is None:
            r = reasons[key] = _Reason(label=description.strip())
        r.uses += 1
        r.weighted_uses += _recency_fit(day, on_date)  # a use months ago barely counts
        # Keep the most recent original casing as the label the user sees.
        if r.last_used is None or day >= r.last_used:
            r.last_used = day
            r.label = description.strip()
        if amt is not None:
            r.amounts.append(Decimal(amt))
        if on_date is not None and day.weekday() == on_date.weekday():
            r.weekday_hits += 1
        if category_id is not None and cat == category_id:
            r.category_hits += 1

    target = Decimal(amount) if amount is not None else None
    scored: list[tuple[float, _Reason]] = []
    for r in reasons.values():
        if r.uses < _MIN_USES:
            continue
        # Base: recency-weighted frequency, damped so a heavy user's top reasons
        # don't drown everything. sqrt keeps 100 fresh uses from being 25x a
        # handful of them.
        base = math.sqrt(r.weighted_uses)
        weekday_fit = r.weekday_hits / r.uses if r.uses else 0.0
        category_fit = r.category_hits / r.uses if (category_id is not None and r.uses) else 0.0
        boost = 1.0 + _W_WEEKDAY * weekday_fit + _W_CATEGORY * category_fit

        # Amount gates the whole thing (see the constant's comment). Neutral
        # when no amount is supplied.
        if target is None:
            gate = 1.0
        else:
            gate = _AMOUNT_GATE_FLOOR + (1.0 - _AMOUNT_GATE_FLOOR) * _amount_fit(r.amounts, target)

        scored.append((base * boost * gate, r))

    scored.sort(key=lambda pair: (-pair[0], -pair[1].weighted_uses, pair[1].label.lower()))
    return [
        {"reason": r.label, "uses": r.uses, "last_used": r.last_used.isoformat() if r.last_used else None}
        for _, r in scored[:limit]
    ]
