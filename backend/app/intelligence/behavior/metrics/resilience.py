"""B1.5b metrics — stress, goal interference, recovery, income concentration.

Behavioural (historical) signals only — the live projection Risk engine stays
separate; the advisor layer merges both. Each reuses the shared aggregates + the
B1.5a trend engine, exposes contributors/culprits where asked, and is cold-start
honest (no stress/recovery claim without enough evidence).
"""

from __future__ import annotations

import statistics
from datetime import date
from decimal import Decimal

from app.intelligence.behavior import aggregates, scoring, trend
from app.intelligence.behavior.data import BehaviorData
from app.intelligence.behavior.registry import (
    ACHIEVEMENT,
    CASHFLOW,
    HIGHER_BETTER,
    INCOME,
    LOWER_BETTER,
    OPPORTUNITY,
    SAVINGS,
    WARNING,
    register,
)

_MIN_MONTHS = 3
_MIN_ROWS = 20
_RECOVERY_WINDOW = 2          # months allowed to bounce back from a dip


def _rows_in(data: BehaviorData, months: tuple) -> int:
    allowed = set(months)
    return sum(1 for e in data.expenses if (e.on.year, e.on.month) in allowed)


def _months_between(start: date, end: date) -> int:
    return max(1, (end.year - start.year) * 12 + (end.month - start.month))


def _month_cutoff(ym: tuple[int, int]) -> date:
    nxt = date(ym[0] + (ym[1] // 12), (ym[1] % 12) + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


# --------------------------------------------------------------------------- #
@register(key="financial_stress_index", dimension=CASHFLOW, direction=LOWER_BETTER,
          forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY))
def financial_stress_index(data: BehaviorData) -> scoring.BehavioralMetric:
    """Historical pressure: exposes the contributors so the advisor explains why."""
    key, dim = "financial_stress_index", CASHFLOW
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS or _rows_in(data, months) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"months": len(months)})
    ref = aggregates.income_reference(data, months)
    if ref <= 0:
        return scoring.insufficient(key, dim, "no_income_reference")

    net = aggregates.net_by_month(data, months)
    exp = aggregates.total_by_month(data, months)
    disc = aggregates.discretionary_by_month(data, months)
    n = len(months)

    contributors: list[tuple[str, float]] = []
    contributors.append(("savings_shortfall", sum(1 for m in months if net[m] < 0) / n))
    if data.monthly_threshold and data.monthly_threshold > 0:
        contributors.append(("threshold_breaches",
                             sum(1 for m in months if exp[m] > data.monthly_threshold) / n))
    recurring = sum((p.amount for p in data.planned if p.is_recurring), Decimal("0"))
    if recurring > 0:
        contributors.append(("recurring_commitments", min(1.0, max(0.0, float(recurring / ref) - 0.30) / 0.40)))
    total = sum(exp.values(), Decimal("0"))
    if total > 0:
        contributors.append(("low_discretionary_room",
                             min(1.0, max(0.0, float(sum(disc.values(), Decimal("0")) / total) - 0.50) / 0.40)))
    mean_exp = scoring.mean_dec([exp[m] for m in months])
    if mean_exp > 0:
        buffer = data.starting_balance + sum(net.values(), Decimal("0"))
        contributors.append(("low_buffer", min(1.0, max(0.0, 1 - float(buffer / (mean_exp * 3))))))

    stress = sum(mag for _, mag in contributors) / len(contributors)
    score = scoring.clamp_score(100 - stress * 100)

    def indicator(m: tuple) -> Decimal:
        ind = (1 if net[m] < 0 else 0)
        if data.monthly_threshold and data.monthly_threshold > 0 and exp[m] > data.monthly_threshold:
            ind += 1
        return Decimal(ind)

    trnd, dur = trend.run_length(trend.series_for_months({m: indicator(m) for m in months}, months), LOWER_BETTER)
    ranked = sorted((c for c in contributors if c[1] > 0), key=lambda c: -c[1])
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(stress, 3))), score=score, confidence="normal",
        trend=trnd, trend_duration_months=dur,
        facts={"stress": round(stress, 3),
               "contributors": [{"name": n_, "magnitude": round(mag, 3)} for n_, mag in ranked]},
    )


# --------------------------------------------------------------------------- #
@register(key="goal_interference_rate", dimension=SAVINGS, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY))
def goal_interference_rate(data: BehaviorData) -> scoring.BehavioralMetric:
    """How often spending kept the user below their goals' required pace — names the culprits."""
    key, dim = "goal_interference_rate", SAVINGS
    active = [g for g in data.goals if g.status == "active"]
    if not active:
        return scoring.insufficient(key, dim, "no_goals")
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS or _rows_in(data, months) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"months": len(months)})

    net = aggregates.net_by_month(data, months)

    def required(m: tuple) -> Decimal:
        cutoff = _month_cutoff(m)
        total = Decimal("0")
        for g in active:
            if g.start_date > cutoff:
                continue
            if g.kind == "monthly_target":
                total += g.target_amount
            elif g.target_date is not None:
                total += g.target_amount / _months_between(cutoff, g.target_date)
        return total

    evaluated, interfering = [], []
    for m in months:
        if any(g.start_date <= _month_cutoff(m) for g in active):
            evaluated.append(m)
            if net[m] < required(m):
                interfering.append(m)
    if len(evaluated) < 2:
        return scoring.insufficient(key, dim, "goals_too_new", {"evaluated": len(evaluated)})

    rate = len(interfering) / len(evaluated)
    score = scoring.clamp_score(100 - rate * 100)

    # culprits: biggest discretionary consumers across the interfering months
    by_cat = aggregates.by_category_by_month(data, tuple(interfering)) if interfering else {}
    spend = []
    for cid, mmap in by_cat.items():
        if data.is_essential(cid):
            continue
        tot = sum(mmap.values(), Decimal("0"))
        if tot > 0:
            info = data.categories.get(cid)
            spend.append({"category": info.name if info else "Uncategorized", "amount": str(tot)})
    spend.sort(key=lambda c: Decimal(c["amount"]), reverse=True)
    events = [p.occasion_type for p in data.planned
              if p.occasion_type and (p.planned_date.year, p.planned_date.month) in set(interfering)]

    ind_map = {m: Decimal(1 if (m in interfering) else 0) for m in evaluated}
    trnd, dur = trend.run_length(trend.series_for_months(ind_map, tuple(evaluated)), LOWER_BETTER)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(rate, 3))), score=score, confidence="normal",
        trend=trnd, trend_duration_months=dur,
        facts={"interference_rate": round(rate, 3), "interfering_months": len(interfering),
               "evaluated_months": len(evaluated), "culprits": spend[:3],
               "has_recurring": any(p.is_recurring for p in data.planned), "events": events[:3]},
    )


# --------------------------------------------------------------------------- #
@register(key="savings_recovery_rate", dimension=SAVINGS, direction=HIGHER_BETTER,
          forward_risk=True, notification_kinds=(WARNING, ACHIEVEMENT))
def savings_recovery_rate(data: BehaviorData) -> scoring.BehavioralMetric:
    """After a negative-savings month, how reliably/quickly the user bounces back."""
    key, dim = "savings_recovery_rate", SAVINGS
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    net = trend.series_for_months(aggregates.net_by_month(data, months), months)
    dips = [i for i in range(len(net) - 1) if net[i] < 0]
    if len(dips) < 2:
        return scoring.insufficient(key, dim, "no_setbacks_to_assess", {"dips": len(dips)})

    speeds, recoveries = [], 0
    for i in dips:
        for k in range(1, _RECOVERY_WINDOW + 1):
            if i + k < len(net) and net[i + k] >= 0:
                recoveries += 1
                speeds.append(k)
                break
    rate = recoveries / len(dips)
    mean_speed = statistics.fmean(speeds) if speeds else None
    score = scoring.clamp_score(rate * 100 - ((mean_speed - 1) * 15 if mean_speed else 0))
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(rate, 3))), score=score, confidence="normal",
        trend="unknown",
        facts={"recovery_rate": round(rate, 3), "dip_events": len(dips), "recoveries": recoveries,
               "mean_recovery_months": round(mean_speed, 2) if mean_speed else None},
    )


# --------------------------------------------------------------------------- #
@register(key="spending_recovery_speed", dimension=CASHFLOW, direction=HIGHER_BETTER,
          forward_risk=True, notification_kinds=(WARNING, ACHIEVEMENT))
def spending_recovery_speed(data: BehaviorData) -> scoring.BehavioralMetric:
    """After a discretionary spike, how fast spending returns to baseline."""
    key, dim = "spending_recovery_speed", CASHFLOW
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    disc = trend.series_for_months(aggregates.discretionary_by_month(data, months), months)
    floats = [float(v) for v in disc]
    baseline = statistics.median(floats)
    if baseline <= 0:
        return scoring.insufficient(key, dim, "no_discretionary_spend")
    spikes = [i for i in range(len(floats) - 1) if floats[i] > baseline * 1.3]
    speeds = []
    for i in spikes:
        for k in range(1, len(floats) - i):
            if floats[i + k] <= baseline * 1.1:
                speeds.append(k)
                break
    if not speeds:
        return scoring.insufficient(key, dim, "no_resolved_spikes", {"spikes": len(spikes)})

    mean_speed = statistics.fmean(speeds)
    score = scoring.clamp_score(100 - (mean_speed - 1) * 25)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(mean_speed, 2))), score=score, confidence="normal",
        trend="unknown",
        facts={"mean_recovery_months": round(mean_speed, 2), "spike_count": len(spikes), "baseline": round(baseline, 2)},
    )


# --------------------------------------------------------------------------- #
@register(key="income_dependency_concentration", dimension=INCOME, direction=LOWER_BETTER,
          forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY))
def income_dependency_concentration(data: BehaviorData) -> scoring.BehavioralMetric:
    """Concentration of income across sources (single-source reliance). HHI."""
    key, dim = "income_dependency_concentration", INCOME
    amounts = [s.amount for s in data.income_sources if s.amount and s.amount > 0]
    if len(amounts) < 2:
        # one source isn't "diversification risk" we should warn on without more signal
        return scoring.insufficient(key, dim, "single_or_no_source", {"sources": len(amounts)})
    total = sum(amounts, Decimal("0"))
    hhi = sum(((a / total) ** 2 for a in amounts), Decimal("0"))
    score = scoring.clamp_score(100 - max(0.0, float(hhi) - 0.50) * 200)
    return scoring.metric(
        key=key, dimension=dim, value=hhi.quantize(Decimal("0.001")), score=score, confidence="normal",
        trend="unknown",
        facts={"hhi": str(hhi.quantize(Decimal("0.001"))), "sources": len(amounts)},
    )
