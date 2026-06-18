"""Feasibility Engine (Budget Intelligence System — Phase 3).

Turns the Reality Engine + country/profile context into a survival-first waterfall,
a success-probability band (never binary), and a structural diagnosis. Deterministic
(no LLM). The emergency buffer is funded BEFORE goals (it protects them).
"""

from __future__ import annotations

import calendar as _cal
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense
from app.models.enums import OptimizationStyle
from app.schemas.budget_reality import BudgetReality
from app.schemas.feasibility import Feasibility, GoalFeasibility, StructuralFlag, WaterfallStep
from app.services import calendar_service, reality_service

_Q = Decimal("0.0001")
_ZERO = Decimal("0")

# Emergency-buffer rate by optimization style (share of income). Aggressive savers
# keep a thin buffer; comfort-first keeps a fat one.
_BUFFER_RATE = {
    OptimizationStyle.aggressive_goal: Decimal("0.03"),
    OptimizationStyle.max_savings: Decimal("0.05"),
    OptimizationStyle.balanced: Decimal("0.07"),
    OptimizationStyle.comfort_first: Decimal("0.10"),
}


def _band(score: int) -> str:
    if score >= 90:
        return "very_high"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    if score >= 30:
        return "low"
    return "very_low"


def _money(cur: str, value: Decimal) -> str:
    return f"{cur} {value:,.0f}"


def _score(target: Decimal, comfortable: Decimal, stretch: Decimal) -> int:
    """Probability a monthly savings target is sustainable, 0..100."""
    if target <= _ZERO:
        return 100
    if comfortable >= target:                       # fits without lifestyle cuts
        head = comfortable - target
        return min(100, 90 + int(10 * head / target))
    if stretch >= target:                           # fits only by trimming lifestyle
        span = stretch - comfortable
        frac = float((target - comfortable) / span) if span > 0 else 1.0
        return int(round(70 - frac * 40))           # 30..70
    over = target - stretch                          # would require cutting essentials
    frac = min(1.0, float(over / stretch)) if stretch > 0 else 1.0
    return max(5, int(round(29 - 24 * frac)))


def _structural(reality: BudgetReality) -> list[StructuralFlag]:
    income = reality.income_total
    flags: list[StructuralFlag] = []
    if income <= _ZERO:
        return flags

    def _ratio(amount: Decimal) -> float:
        return float((amount / income).quantize(Decimal("0.001")))

    # Housing.
    hr = reality.housing_ratio
    if hr >= 0.35:
        sev = "high" if hr >= 0.5 else "elevated"
        flags.append(StructuralFlag(kind="housing_ratio", ratio=hr, severity=sev,
            message=f"Housing is {hr*100:.0f}% of your income — "
                    + ("that's a lot; it's the main pressure on your budget." if sev == "high"
                       else "on the higher side.")))

    # Transport (protected essential-living lines that look like transport).
    transport = sum((ln.monthly for ln in reality.protected.lines
                     if "transport" in ln.label.lower()), _ZERO)
    tr = _ratio(transport)
    if tr >= 0.15:
        sev = "high" if tr >= 0.25 else "elevated"
        flags.append(StructuralFlag(kind="transport_ratio", ratio=tr, severity=sev,
            message=f"Transport is {tr*100:.0f}% of your income."))

    # Subscriptions (adjustable lines that came from recurring rules).
    subs = sum((ln.monthly for ln in reality.adjustable.lines if ln.origin == "recurring"), _ZERO)
    sr = _ratio(subs)
    if sr >= 0.08:
        sev = "high" if sr >= 0.15 else "elevated"
        flags.append(StructuralFlag(kind="subscription_ratio", ratio=sr, severity=sev,
            message=f"Subscriptions are {sr*100:.0f}% of your income — easy to trim if you need room."))
    return flags


async def _anomalies(db: AsyncSession, user_id: uuid.UUID, today, cur: str) -> list[str]:
    """Recognise an unusually heavy month vs the trailing average (so we don't treat
    a one-off spike as the norm). Needs history; new users get nothing."""
    month_start = today.replace(day=1)
    this_month = Decimal(await db.scalar(
        select(func.coalesce(func.sum(Expense.converted_amount), 0)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None),
            Expense.expense_date >= month_start, Expense.expense_date <= today)) or 0)
    prior_start = month_start - timedelta(days=120)
    prior_sum = Decimal(await db.scalar(
        select(func.coalesce(func.sum(Expense.converted_amount), 0)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None),
            Expense.expense_date >= prior_start, Expense.expense_date < month_start)) or 0)
    prior_avg = (prior_sum / 4) if prior_sum > _ZERO else _ZERO
    out: list[str] = []
    if prior_avg > _ZERO and this_month > prior_avg * Decimal("1.3"):
        out.append(f"This month's spending so far ({_money(cur, this_month)}) is well above your "
                   f"usual ~{_money(cur, prior_avg)}/month — it looks like an unusual month, "
                   f"so I won't treat it as your normal baseline.")
    return out


async def assess(db: AsyncSession, user_id: uuid.UUID) -> Feasibility:
    reality = await reality_service.build(db, user_id)
    today = await calendar_service.user_today(db, user_id)
    cur = reality.base_currency
    style = OptimizationStyle(reality.optimization_style)

    income = reality.income_total
    essentials = reality.essentials_total
    lifestyle = reality.adjustable.total
    buffer = (income * _BUFFER_RATE[style]).quantize(_Q)

    comfortable = (income - essentials - buffer - lifestyle).quantize(_Q)
    stretch = (income - essentials - buffer).quantize(_Q)

    # Waterfall: fund survival first, buffer before goals, lifestyle last.
    essential_living = (reality.protected.total - reality.housing_total).quantize(_Q)
    goals_target = reality.goals.total
    steps_def = [
        ("Income", income, False),
        ("Essential living", essential_living, True),
        ("Housing", reality.housing_total, True),
        ("Committed", reality.committed.total, True),
        ("Emergency buffer", buffer, True),
        ("Goals", goals_target, True),
        ("Lifestyle", lifestyle, True),
    ]
    waterfall: list[WaterfallStep] = []
    remaining = _ZERO
    for label, amount, subtract in steps_def:
        remaining = amount if not subtract else (remaining - amount)
        waterfall.append(WaterfallStep(label=label, amount=amount.quantize(_Q),
                                       running_remaining=remaining.quantize(_Q)))

    # Per-goal feasibility.
    goals: list[GoalFeasibility] = []
    for line in reality.goals.lines:
        t = line.monthly
        score = _score(t, comfortable, stretch)
        if comfortable >= t:
            reason = (f"After essentials ({_money(cur, essentials)}) and a {_money(cur, buffer)} buffer, "
                      f"about {_money(cur, comfortable)} is comfortably available — your {_money(cur, t)} "
                      f"target fits with room to spare.")
        elif stretch >= t:
            reason = (f"You can comfortably save {_money(cur, comfortable)}. Reaching {_money(cur, t)} "
                      f"means trimming some lifestyle/adjustable spending (up to {_money(cur, stretch)} is possible).")
        else:
            short = (t - stretch).quantize(_Q)
            reason = (f"Even after cutting all lifestyle, about {_money(cur, stretch)} is available — "
                      f"{_money(cur, t)} would need {_money(cur, short)} more, which means cutting essentials "
                      f"like food. I won't recommend that; let's aim lower or grow income.")
        goals.append(GoalFeasibility(goal=line.label, target_monthly=t.quantize(_Q),
                                     probability_band=_band(score), probability_score=score, reason=reason))

    # Overall band.
    if income <= _ZERO:
        overall = "low"
        summary = "Tell me your income and a goal, and I'll tell you how realistic it is — with the math."
    elif goals:
        worst = min(g.probability_score for g in goals)
        overall = _band(worst)
        summary = (f"{_money(cur, comfortable)} is comfortably available each month "
                   f"after essentials and a {_money(cur, buffer)} buffer.")
    else:
        overall = "very_high" if comfortable > _ZERO else "low"
        summary = (f"After essentials and a {_money(cur, buffer)} buffer, about {_money(cur, comfortable)} "
                   f"is free each month — set a savings goal and I'll plan it.")

    return Feasibility(
        base_currency=cur, optimization_style=style.value,
        income_total=income, essentials_total=essentials, emergency_buffer=buffer,
        lifestyle_total=lifestyle, comfortable_surplus=comfortable, stretch_surplus=stretch,
        waterfall=waterfall, goals=goals, overall_band=overall,
        structural_flags=_structural(reality),
        anomalies=await _anomalies(db, user_id, today, cur),
        summary=summary,
    )
