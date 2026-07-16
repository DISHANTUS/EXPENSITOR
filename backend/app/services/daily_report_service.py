"""End-of-day report — "here's how today went, and what it did for your goal".

Derive-on-read like everything else: nothing is stored, nothing is scheduled.
The report is computed from the same budget summary and savings engine the rest
of the app uses, so it can never quietly disagree with the Plan screen about the
same goal.

Two honesty rules shape this whole module:

1. Nothing is "saved" until the day is actually over. At 2pm, "you saved ₹200
   today" is a guess about the evening — the user can still blow it at dinner.
   Before the cutoff the report says "so far today" and the language stays
   provisional; only after it does the day get called.
2. Under-budget is not the same as money set aside. This reports the gap between
   the daily allowance and what was spent, which is exactly what it says on the
   tin — it never claims the money moved anywhere.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.savings_goal import SavingsGoalKind, SavingsGoalStatus
from app.models.user import User
from app.services import budget_service, calendar_service, savings_service

# The hour (device-local) from which the day is treated as done and the report
# stops hedging. Deliberately late: an evening meal is the classic thing that
# turns a "saved" day into an over one.
DAY_DONE_HOUR = 20

# How far back the multi-day total looks, today included.
WINDOW_DAYS = 7

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


def _streak(
    spend: dict[date, Decimal],
    allowance: Decimal,
    today: date,
    *,
    day_done: bool,
    history_start: date,
) -> int:
    """Consecutive days up to and including today that came in under the
    allowance.

    Two boundaries, both load-bearing. Today only counts once it's actually
    over — a streak including a day still in progress is a promise, not a fact.
    And nothing before `history_start` counts at all: a user who joined
    yesterday has not been under budget for 400 days.

    Within the account's lifetime a day with no expenses DOES count — not
    spending is the thing we're measuring."""
    if allowance <= _ZERO:
        return 0
    streak = 0
    day = today if day_done else today - timedelta(days=1)
    while day >= history_start:
        if spend.get(day, _ZERO) > allowance:
            break
        streak += 1
        day -= timedelta(days=1)
    return streak


async def _history_start(db: AsyncSession, user_id: uuid.UUID, today: date) -> date:
    """The first day this account could possibly have had a spending day —
    i.e. the day it was created. Days before it aren't "under budget", they're
    days that didn't happen."""
    created = await db.scalar(select(User.created_at).where(User.id == user_id))
    if created is None:
        return today
    start = created.date()
    return min(start, today)  # a clock skew must never push the floor past today


async def _nearest_goal(db: AsyncSession, user_id: uuid.UUID, today: date) -> dict[str, Any] | None:
    """The one-off goal with the soonest deadline, with its numbers taken from
    the savings engine rather than recomputed here — two surfaces disagreeing
    about the same goal is worse than showing no goal at all."""
    goals, _ = await savings_service.list_(db, user_id, limit=50, offset=0, status=SavingsGoalStatus.active)
    dated = [g for g in goals if g.kind == SavingsGoalKind.custom_goal and g.target_date is not None]
    if not dated:
        return None
    goal = min(dated, key=lambda g: g.target_date)  # type: ignore[arg-type,return-value]

    state = (await savings_service.get_state(db, user_id, goal.id, today=today))["state"]
    target = Decimal(state["target_amount"])
    progress = Decimal(state["progress"])
    remaining = (target * (Decimal("1") - progress)).quantize(_Q)
    days_left = (goal.target_date - today).days if goal.target_date else None

    return {
        "id": str(goal.id),
        "name": goal.name,
        "target_amount": str(target.quantize(_Q)),
        "remaining": str(max(_ZERO, remaining)),
        "days_left": days_left,
        "required_daily_saving": state.get("required_daily_saving"),
        "status": state.get("status"),
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
    }


def _money(amount: Decimal, currency: str) -> str:
    whole = amount.quantize(_Q)
    text = f"{whole:,.0f}" if whole == whole.to_integral_value() else f"{whole:,.2f}"
    return f"{currency} {text}"


def _lines(
    *,
    currency: str,
    allowance: Decimal,
    spent_today: Decimal,
    saved_today: Decimal,
    day_done: bool,
    streak: int,
    window_net: Decimal,
    window_days: int,
    goal: dict[str, Any] | None,
) -> list[str]:
    """The report in words. Every sentence is a restatement of a number above —
    no advice, no encouragement it hasn't earned."""
    out: list[str] = []
    when = "today" if day_done else "so far today"

    if allowance <= _ZERO:
        # No income on file yet, so there's no allowance to compare against —
        # but the goal still gets its line. An early return here meant anyone
        # who hadn't entered their income never saw their goal in the report,
        # which is exactly the person most likely to have set one.
        out.append(f"You've spent {_money(spent_today, currency)} {when}.")
        out.append("Once I know your income and commitments, I can tell you how that compares to a daily allowance.")
        out.extend(_goal_lines(goal, currency))
        return out

    if saved_today > _ZERO:
        verb = "came in" if day_done else "you're"
        out.append(
            f"{'You' if day_done else 'So far'} {verb} {_money(saved_today, currency)} under your "
            f"{_money(allowance, currency)} allowance {'today' if day_done else 'for today'}."
        )
    elif saved_today < _ZERO:
        out.append(
            f"You're {_money(-saved_today, currency)} over your {_money(allowance, currency)} allowance {when}."
        )
    else:
        out.append(f"You've spent exactly your {_money(allowance, currency)} allowance {when}.")

    if streak >= 2:
        out.append(f"That's {streak} days in a row under budget.")

    # A "multi-day total" over one day is just the line above said twice — and
    # it reads "the last 1 days". Needs at least two days to be worth saying.
    if window_days >= 2 and window_net != _ZERO:
        direction = "under" if window_net > _ZERO else "over"
        out.append(
            f"Across the last {window_days} days you're {_money(abs(window_net), currency)} {direction} budget overall."
        )

    out.extend(_goal_lines(goal, currency))
    return out


def _goal_lines(goal: dict[str, Any] | None, currency: str) -> list[str]:
    if not goal:
        return []
    remaining = Decimal(goal["remaining"])
    name = goal["name"]
    if remaining <= _ZERO:
        return [f"You've already got what you need for {name}."]
    days_left = goal.get("days_left")
    tail = ""
    if isinstance(days_left, int) and days_left > 0:
        tail = f", {days_left} days out"
    elif isinstance(days_left, int) and days_left <= 0:
        tail = ", and the date you picked has passed"
    return [f"Still {_money(remaining, currency)} to go for {name}{tail}."]


async def report(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    today: date | None = None,
    hour: int | None = None,
) -> dict[str, Any]:
    """`hour` is the device-local hour (the client sends it, same as greetings
    do) — the server's clock is the wrong one to decide whether someone's day is
    over. With no hour, assume the day is NOT done and keep the language
    provisional; over-claiming is the worse failure."""
    today = today or await calendar_service.user_today(db, user_id)
    day_done = hour is not None and hour >= DAY_DONE_HOUR

    budget = await budget_service.summary(db, user_id)
    allowance = Decimal(budget.daily_budget or 0)
    currency = budget.base_currency

    # Nothing before the account existed can be counted as a day under budget.
    # Without this floor a user who joined today is congratulated for six days
    # of thrift they were never here for — the totals are pure fabrication, and
    # they'd contradict the streak, which already refuses to count empty days.
    history_start = await _history_start(db, user_id, today)

    window_start = max(today - timedelta(days=WINDOW_DAYS - 1), history_start)
    spend = await _spend_by_day(db, user_id, window_start, today)

    spent_today = spend.get(today, _ZERO)
    saved_today = (allowance - spent_today).quantize(_Q)

    # The multi-day total measures every day against TODAY'S allowance. It's an
    # approximation — the allowance moves when income or commitments change —
    # but re-deriving a historical allowance per day would be a bigger lie
    # dressed as precision, since we never stored what it was back then.
    span = (today - window_start).days + 1
    counted_days = [window_start + timedelta(days=i) for i in range(span)]
    if not day_done:
        counted_days = [d for d in counted_days if d != today]
    window_net = sum((allowance - spend.get(d, _ZERO) for d in counted_days), _ZERO).quantize(_Q)

    streak = _streak(spend, allowance, today, day_done=day_done, history_start=history_start)
    goal = await _nearest_goal(db, user_id, today)

    return {
        "date": today.isoformat(),
        "currency": currency,
        "day_done": day_done,
        "daily_allowance": str(allowance.quantize(_Q)),
        "spent_today": str(spent_today.quantize(_Q)),
        "saved_today": str(saved_today),
        "status": "over" if saved_today < _ZERO else "under" if saved_today > _ZERO else "even",
        "streak_days": streak,
        "window_days": len(counted_days),
        "window_net": str(window_net),
        "goal": goal,
        "lines": _lines(
            currency=currency,
            allowance=allowance,
            spent_today=spent_today,
            saved_today=saved_today,
            day_done=day_done,
            streak=streak,
            window_net=window_net,
            window_days=len(counted_days),
            goal=goal,
        ),
    }
