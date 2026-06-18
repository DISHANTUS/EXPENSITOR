"""Home "thought" (UI-X — Advary's Room).

A short, contextual reflection for the top of Home — goal status, who owes you,
the next life milestone — composed deterministically from existing state, plus a
mood for the orb to wear. Resilient: degrades to a warm default, never errors.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Receivable, SavingsGoal
from app.models.enums import ReceivableKind, ReceivableStatus, SavingsGoalKind, SavingsGoalStatus
from app.services import (
    calendar_service,
    facts_service,
    feasibility_service,
    forecast_service,
    profile_service,
    settings_service,
)

_ZERO = Decimal("0")
_COUNTRY = {"IN": "India", "JP": "Japan", "US": "the US", "GB": "the UK"}
_POSITIVE = {"very_high", "high"}


def _money(cur: str, v: Decimal) -> str:
    return f"{cur} {v:,.0f}"


def _months_until(today, target) -> int:
    return max(1, (target.year - today.year) * 12 + (target.month - today.month))


async def _goal_line(db: AsyncSession, user_id: uuid.UUID, cur: str, today) -> tuple[str, str] | None:
    """A specific, deterministic line about the primary goal. A DATED goal is
    measured against the real forecast ETA (ahead/behind by N days), or the pace
    it needs by its target month; an undated monthly-target goal uses its
    feasibility band + pace. Returns (line, mood) or None when there are no goals."""
    active = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.active))).scalars().all()
    if not active:
        return None

    # Prefer a dated goal (it has a deadline to be ahead/behind of); else the soonest.
    dated = sorted((g for g in active if g.target_date), key=lambda g: g.target_date)
    if dated:
        goal = dated[0]
        target = goal.target_date
        eta = None
        try:
            fc = await forecast_service.forecast(db, user_id, goal_id=str(goal.id), question="home")
            cp = fc.future_me.current_path if fc and fc.future_me else None
            eta = cp.eta if cp else None
        except Exception:  # noqa: BLE001 — the forecast must never break the thought
            eta = None
        if eta is not None:
            days = (target - eta).days
            if days >= 7:
                return (f"Your {goal.name} is ahead of schedule — about {days} days early at your current pace.", "celebrating")
            if days <= -7:
                needed = (goal.converted_amount / _months_until(today, target)).quantize(Decimal("1"))
                return (f"Your {goal.name} is ~{abs(days)} days behind — around {_money(cur, needed)}/month gets it back on track.", "concerned")
            return (f"Your {goal.name} is right on track for {eta:%b %Y}.", "idle")
        # Not enough history to forecast yet — show the monthly pace toward the date.
        needed = (goal.converted_amount / _months_until(today, target)).quantize(Decimal("1"))
        return (f"Your {goal.name} — about {_money(cur, needed)}/month reaches it by {target:%b %Y}.", "idle")

    # Undated monthly-target goal — use the feasibility band + monthly pace.
    feas = await feasibility_service.assess(db, user_id)
    if not feas.goals:
        return None
    g = feas.goals[0]
    rate = _money(cur, g.target_monthly)
    if g.probability_band in _POSITIVE:
        return (f"Your {g.goal} is on track — about {rate}/month keeps you on pace.", "celebrating")
    if g.probability_band == "medium":
        return (f"Your {g.goal} is within reach — around {rate}/month gets you there.", "idle")
    return (f"Your {g.goal} needs attention — it'd take about {rate}/month. Let's look at the plan.", "concerned")


async def build(db: AsyncSession, user_id: uuid.UUID) -> dict:
    today = await calendar_service.user_today(db, user_id)
    cur = (await settings_service.get_settings(db, user_id)).base_currency
    profile = await profile_service.get_profile(db, user_id)

    lines: list[str] = []
    mood = "idle"

    # 1) Goal status — specific (ahead/behind by N days, or the pace it needs).
    goal_line = await _goal_line(db, user_id, cur, today)
    if goal_line is not None:
        lines.append(goal_line[0])
        mood = goal_line[1]

    # 2) Who owes you (receivables).
    pending = (await db.execute(select(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.status == ReceivableStatus.pending).order_by(Receivable.expected_date))).scalars().all()
    if pending:
        total = sum((r.converted_amount for r in pending), _ZERO)
        overdue = [r for r in pending if r.kind == ReceivableKind.one_time
                   and r.expected_date and r.expected_date < today]
        if len(pending) == 1:
            r = pending[0]
            tail = " — that one's overdue." if overdue else " No urgency right now."
            lines.append(f"{r.source_name} still owes you {_money(cur, r.converted_amount)}.{tail}")
        else:
            tail = f" {len(overdue)} overdue." if overdue else ""
            lines.append(f"{len(pending)} people owe you {_money(cur, total)}.{tail}")
        if overdue:
            mood = "concerned"

    # 3) Next life milestone (future move).
    if profile.moving_country and profile.future_country:
        where = _COUNTRY.get(profile.future_country, profile.future_country)
        when = f" in {profile.future_move_year}" if profile.future_move_year else ""
        lines.append(f"Next up: moving to {where}{when}.")

    # Last resort — nothing user-specific to say. A fun fact is friendlier than a
    # filler line, but it only ever appears here, after everything about the user.
    if not lines:
        fact = facts_service.fallback_thought(today)
        lines.append(fact or "Nothing pressing today — a good day to get a little ahead.")

    return {"lines": lines, "mood": mood}
