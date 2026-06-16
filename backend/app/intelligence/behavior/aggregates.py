"""Shared monthly aggregates for B1.5 metrics (pure, over BehaviorData).

Each helper returns a {YearMonth: Decimal} map (or per-category nesting) so the
trend engine + B1.5 metrics read consistent monthly series. Computed from the
already-loaded window — no new queries. (The precompute-once optimisation is
deferred to B1.5c when the window widens to 13 months.)
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.intelligence.behavior.data import BehaviorData, YearMonth

EARLY = Decimal("0")


def total_by_month(data: BehaviorData, months: tuple[YearMonth, ...]) -> dict[YearMonth, Decimal]:
    out = {ym: Decimal("0") for ym in months}
    allowed = set(months)
    for e in data.expenses:
        ym = (e.on.year, e.on.month)
        if ym in allowed:
            out[ym] += e.amount
    return out


def discretionary_by_month(data: BehaviorData, months: tuple[YearMonth, ...]) -> dict[YearMonth, Decimal]:
    out = {ym: Decimal("0") for ym in months}
    allowed = set(months)
    for e in data.expenses:
        ym = (e.on.year, e.on.month)
        if ym in allowed and not data.is_essential(e.category_id):
            out[ym] += e.amount
    return out


def by_category_by_month(
    data: BehaviorData, months: tuple[YearMonth, ...]
) -> dict[uuid.UUID | None, dict[YearMonth, Decimal]]:
    allowed = set(months)
    out: dict[uuid.UUID | None, dict[YearMonth, Decimal]] = {}
    for e in data.expenses:
        ym = (e.on.year, e.on.month)
        if ym not in allowed:
            continue
        out.setdefault(e.category_id, {m: Decimal("0") for m in months})[ym] += e.amount
    return out


def cumulative_recurring_by_month(data: BehaviorData, months: tuple[YearMonth, ...]) -> dict[YearMonth, Decimal]:
    """Recurring commitments active as of each month (commitment accumulation)."""
    out: dict[YearMonth, Decimal] = {}
    for ym in months:
        # last day of the month is enough as a cut-off for "active by then"
        next_month = date(ym[0] + (ym[1] // 12), (ym[1] % 12) + 1, 1)
        cutoff = date.fromordinal(next_month.toordinal() - 1)
        out[ym] = sum(
            (p.amount for p in data.planned if p.is_recurring and p.planned_date <= cutoff),
            Decimal("0"),
        )
    return out


def net_by_month(data: BehaviorData, months: tuple[YearMonth, ...]) -> dict[YearMonth, Decimal]:
    """Net savings per month (income - expense)."""
    inc = {ym: Decimal("0") for ym in months}
    exp = {ym: Decimal("0") for ym in months}
    allowed = set(months)
    for i in data.incomes:
        ym = (i.on.year, i.on.month)
        if ym in allowed:
            inc[ym] += i.amount
    for e in data.expenses:
        ym = (e.on.year, e.on.month)
        if ym in allowed:
            exp[ym] += e.amount
    return {ym: inc[ym] - exp[ym] for ym in months}


def income_reference(data: BehaviorData, months: tuple[YearMonth, ...]) -> Decimal:
    """A stable monthly income denominator: explicit estimate, else mean monthly income."""
    if data.monthly_income_estimate and data.monthly_income_estimate > 0:
        return data.monthly_income_estimate
    totals = {ym: Decimal("0") for ym in months}
    allowed = set(months)
    for i in data.incomes:
        ym = (i.on.year, i.on.month)
        if ym in allowed:
            totals[ym] += i.amount
    vals = [v for v in totals.values() if v > 0]
    return (sum(vals, Decimal("0")) / len(vals)) if vals else Decimal("0")
