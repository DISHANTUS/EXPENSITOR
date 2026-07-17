"""Festivals, and what they actually cost THIS user.

The whole point is the second half. "Diwali is on 8 November" is a calendar; any
phone does that. What's worth saying is "last Diwali that fortnight cost you
₹4,200 more than your normal fortnight" — because that's the number that makes
someone start putting money aside now.

So the rules here are:
  - the DATE comes from the checked-in calendar (real, sourced, verifiable)
  - the MONEY comes only from the user's own ledger — measured, never modelled,
    never a national average, never a guess about "what people spend on Diwali"
  - with no history for a festival, it says the date and stops. An invented
    number attached to a real date is the most convincing kind of wrong.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.companion import festival_calendar as fc
from app.models.expense import Expense
from app.models.user import User
from app.services import budget_service, calendar_service

# A festival window is compared against the ordinary days around it. This is the
# stretch either side used to work out what "ordinary" costs for this person.
BASELINE_DAYS = 28

# Below this, a "baseline" is one or two days of noise, and the comparison would
# be arithmetic dressed up as insight.
MIN_BASELINE_DAYS = 10

# Don't cry wolf over rounding. A festival week has to be meaningfully dearer
# than a normal one before it's worth mentioning.
MIN_UPLIFT_RATIO = Decimal("1.15")

_Q = Decimal("0.01")
_ZERO = Decimal("0")


async def _spend_by_day(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> dict[date, Decimal]:
    rows = await db.execute(
        select(Expense.expense_date, func.coalesce(func.sum(Expense.converted_amount), 0))
        .where(
            Expense.user_id == user_id,
            Expense.deleted_at.is_(None),
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .group_by(Expense.expense_date)
    )
    return {row[0]: Decimal(row[1] or 0) for row in rows}


async def _history_start(db: AsyncSession, user_id: uuid.UUID, today: date) -> date:
    created = await db.scalar(select(User.created_at).where(User.id == user_id))
    return min(created.date(), today) if created else today


async def _measure(
    db: AsyncSession, user_id: uuid.UUID, festival: fc.Festival, *, history_start: date
) -> dict[str, Any] | None:
    """What this festival cost, against what a normal stretch costs this person.

    Returns None whenever the honest answer is "I don't know" — the window
    predates the account, or there aren't enough ordinary days either side to
    know what ordinary looks like."""
    start, end = fc.window(festival)
    if start < history_start:
        return None  # the account wasn't here for it; there is nothing to measure

    span_start = max(start - timedelta(days=BASELINE_DAYS), history_start)
    span_end = end + timedelta(days=BASELINE_DAYS)
    spend = await _spend_by_day(db, user_id, span_start, span_end)

    festival_window = {start + timedelta(days=i) for i in range((end - start).days + 1)}
    # Any day belonging to ANY festival is not an ordinary day. Without this,
    # Diwali gets measured against a baseline stuffed with Navratri and Dussehra
    # spending and comes out looking cheap — the comparison quietly eats the
    # very thing it's meant to reveal.
    busy_days = fc.all_festival_days(region=festival.region)

    festival_days = len(festival_window)
    festival_spend = sum((spend.get(d, _ZERO) for d in festival_window), _ZERO)

    baseline_days = 0
    baseline_spend = _ZERO
    for offset in range((span_end - span_start).days + 1):
        day = span_start + timedelta(days=offset)
        if day in festival_window or day in busy_days:
            continue
        baseline_days += 1
        baseline_spend += spend.get(day, _ZERO)

    if baseline_days < MIN_BASELINE_DAYS or festival_days <= 0:
        return None

    festival_daily = festival_spend / Decimal(festival_days)
    baseline_daily = baseline_spend / Decimal(baseline_days)
    if baseline_daily <= _ZERO:
        return None  # nothing to compare against; a ratio here would be meaningless

    extra = ((festival_daily - baseline_daily) * Decimal(festival_days)).quantize(_Q)
    ratio = festival_daily / baseline_daily

    return {
        "festival": festival.name,
        "year": festival.day.year,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "window_days": festival_days,
        "spent": str(festival_spend.quantize(_Q)),
        "usual_for_that_many_days": str((baseline_daily * Decimal(festival_days)).quantize(_Q)),
        "extra": str(extra),
        "ratio": str(ratio.quantize(Decimal("0.01"))),
        "notable": ratio >= MIN_UPLIFT_RATIO and extra > _ZERO,
    }


def _money(amount: Decimal, currency: str) -> str:
    whole = amount.quantize(_Q)
    text = f"{whole:,.0f}" if whole == whole.to_integral_value() else f"{whole:,.2f}"
    return f"{currency} {text}"


def _line(festival: fc.Festival, days_away: int, measured: dict[str, Any] | None, currency: str) -> str:
    when = (
        "today" if days_away == 0
        else "tomorrow" if days_away == 1
        else f"in {days_away} days"
    )
    hedge = " (the exact date depends on the moon sighting)" if festival.approximate else ""
    base = f"{festival.name} is {when}{hedge}."

    if measured and measured["notable"]:
        extra = Decimal(measured["extra"])
        return (
            f"{base} Last time, that stretch cost you {_money(extra, currency)} more "
            f"than your usual {measured['window_days']} days."
        )
    if measured:
        # Measured and it wasn't a spike. Saying so is worth more than silence —
        # it's the answer to "should I be worried about this one?".
        return f"{base} Last time it didn't cost you much more than a normal stretch."
    return base  # no history: the date, and not one invented rupee


async def insights(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None, limit: int = 3
) -> dict[str, Any]:
    today = today or await calendar_service.user_today(db, user_id)

    # Which festivals are even this user's. Derived from the currency they think
    # in — a proxy, but one that needs no migration and no location permission.
    # An unmapped currency gets no festivals at all, which is the honest answer:
    # showing a Brazilian user Diwali would be worse than showing them nothing.
    settings = await budget_service.summary(db, user_id)
    region = fc.region_for_currency(settings.base_currency)
    if region is None:
        return {
            "ready": False,
            "reason": "no_festival_calendar_for_region",
            "calendar_until": fc.LAST_COVERED_DATE.isoformat(),
            "upcoming": [],
        }

    if not fc.covers(today, region=region):
        # The baked calendar has run out. Say so plainly — a festival feature
        # that starts guessing dates is worse than one that admits it's stale.
        return {
            "ready": False,
            "reason": "festival_calendar_out_of_date",
            "calendar_until": fc.coverage(region)[1].isoformat(),
            "upcoming": [],
        }

    budget = settings
    currency = budget.base_currency
    history_start = await _history_start(db, user_id, today)

    out: list[dict[str, Any]] = []
    for festival in fc.upcoming(today, region=region)[:limit]:
        previous = fc.previous_occurrence(festival.name, festival.day)
        measured = (
            await _measure(db, user_id, previous, history_start=history_start) if previous else None
        )
        days_away = (festival.day - today).days
        out.append({
            "name": festival.name,
            "date": festival.day.isoformat(),
            "days_away": days_away,
            "approximate": festival.approximate,
            "last_time": measured,
            "line": _line(festival, days_away, measured, currency),
        })

    return {
        "ready": True,
        "currency": currency,
        "region": region,
        "calendar_until": fc.coverage(region)[1].isoformat(),
        "upcoming": out,
    }
