"""B1.5c metrics — payday timing, planning execution, forecastability, impulse,
seasonality, savings-forecast reliability, and offer-exposure proxy.

Behavioural + deterministic. Descriptive metrics (seasonal, offer proxy) are
context only — excluded from scoring/SWOR/signals (see scoring.build_*), surfaced
in to_facts / advisor_view / behavioral_memory. Cold-start honest throughout.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior import aggregates, scoring, trend
from app.intelligence.behavior.data import BehaviorData
from app.intelligence.behavior.registry import (
    ACHIEVEMENT,
    DESCRIPTIVE,
    DISCIPLINE,
    HIGHER_BETTER,
    LIFESTYLE,
    LOWER_BETTER,
    OPPORTUNITY,
    PLANNING,
    REMINDER,
    SAVINGS,
    WARNING,
    register,
)

_MIN_MONTHS = 3
_MIN_ROWS = 20
_MIN_DECISIONS = 4
_SEASONAL_MIN_MONTHS = 12


def _rows_in(data: BehaviorData, months: tuple) -> int:
    allowed = set(months)
    return sum(1 for e in data.expenses if (e.on.year, e.on.month) in allowed)


def _month_cutoff(ym: tuple[int, int]) -> date:
    nxt = date(ym[0] + (ym[1] // 12), (ym[1] % 12) + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def _salary_occurrences(data: BehaviorData, start: date, end: date) -> list[date]:
    from app.intelligence.projection.calendar_utils import clamp_day, iter_year_months
    out: list[date] = []
    for d in data.salary_days:
        for year, month in iter_year_months(start, end):
            occ = clamp_day(year, month, d)
            if start <= occ <= end:
                out.append(occ)
    return sorted(out)


# --------------------------------------------------------------------------- #
@register(key="payday_decay", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY),
          personality_tags=("impulse_buyer",))
def payday_decay(data: BehaviorData) -> scoring.BehavioralMetric:
    """How front-loaded spending is across the pay cycle (money vanishing fast)."""
    key, dim = "payday_decay", DISCIPLINE
    if not data.salary_days:
        return scoring.insufficient(key, dim, "no_salary_data")
    rows = data.expenses_in_rate_window()
    if len(rows) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})
    occ = _salary_occurrences(data, data.window.rate_start, data.window.today)
    if len(occ) < 2:
        return scoring.insufficient(key, dim, "too_few_cycles", {"cycles": len(occ)})

    shares: list[Decimal] = []
    for i, o in enumerate(occ):
        nxt = occ[i + 1] if i + 1 < len(occ) else o + timedelta(days=30)
        cycle = [e for e in rows if o <= e.on < nxt]
        total = sum((e.amount for e in cycle), Decimal("0"))
        if total <= 0:
            continue
        first3 = sum((e.amount for e in cycle if (e.on - o).days <= 2), Decimal("0"))
        shares.append(first3 / total)
    if len(shares) < 2:
        return scoring.insufficient(key, dim, "insufficient_data", {"cycles": len(shares)})

    front = scoring.mean_dec(shares)   # share of each cycle spent in its first 3 days
    score = scoring.clamp_score(100 - max(0.0, float(front) - 0.30) * 200)
    trnd, dur = trend.run_length(shares, LOWER_BETTER)
    return scoring.metric(
        key=key, dimension=dim, value=front.quantize(Decimal("0.001")), score=score, confidence="normal",
        trend=trnd, trend_duration_months=dur,
        facts={"front_load_share": str(front.quantize(Decimal("0.001"))), "cycles": len(shares)},
    )


# --------------------------------------------------------------------------- #
@register(key="planned_vs_actual_drift", dimension=PLANNING, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY))
def planned_vs_actual_drift(data: BehaviorData) -> scoring.BehavioralMetric:
    """Execution reliability: did actual spend drift above what was planned, and trending?"""
    key, dim = "planned_vs_actual_drift", PLANNING
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    allowed = set(months)
    planned_by = {ym: Decimal("0") for ym in months}
    for p in data.planned:
        ym = (p.planned_date.year, p.planned_date.month)
        if ym in allowed:
            planned_by[ym] += p.amount
    actual = aggregates.total_by_month(data, months)

    valid = [ym for ym in months if planned_by[ym] > 0]
    if len(valid) < 2:
        return scoring.insufficient(key, dim, "insufficient_planned_data", {"months": len(valid)})
    drift = {ym: (actual[ym] - planned_by[ym]) / planned_by[ym] for ym in valid}
    mean_drift = scoring.mean_dec([drift[ym] for ym in valid])
    score = scoring.clamp_score(100 - max(0.0, float(mean_drift)) * 100)
    trnd, dur = trend.run_length([drift[ym] for ym in valid], LOWER_BETTER)
    return scoring.metric(
        key=key, dimension=dim, value=mean_drift.quantize(Decimal("0.001")), score=score, confidence="normal",
        trend=trnd, trend_duration_months=dur,
        facts={"mean_drift": str(mean_drift.quantize(Decimal("0.001"))), "months_evaluated": len(valid)},
    )


# --------------------------------------------------------------------------- #
@register(key="expense_prediction_accuracy", dimension=PLANNING, direction=HIGHER_BETTER,
          notification_kinds=(OPPORTUNITY, ACHIEVEMENT))
def expense_prediction_accuracy(data: BehaviorData) -> scoring.BehavioralMetric:
    """How well a simple rolling forecast predicts actual monthly spend (predictability)."""
    key, dim = "expense_prediction_accuracy", PLANNING
    months = data.window.complete_months
    if len(months) < 4:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    series = [aggregates.total_by_month(data, months)[m] for m in months]
    errors = []
    for i in range(3, len(series)):
        forecast = scoring.mean_dec(series[i - 3:i])
        actual = series[i]
        if actual > 0:
            errors.append(abs(float(actual - forecast)) / float(actual))
    if not errors:
        return scoring.insufficient(key, dim, "insufficient_data")
    accuracy = max(0.0, 1 - sum(errors) / len(errors))
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(accuracy, 3))), score=scoring.clamp_score(accuracy * 100),
        confidence="normal", trend="unknown",
        facts={"accuracy": round(accuracy, 3), "months": len(months)},
    )


# --------------------------------------------------------------------------- #
@register(key="impulse_purchase_signals", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY),
          personality_tags=("impulse_buyer",))
def impulse_purchase_signals(data: BehaviorData) -> scoring.BehavioralMetric:
    """Timing-based impulse proxy: same-day discretionary clusters. (Offer/delivery-
    driven impulse is deferred until the purchase-outcome log exists.)"""
    key, dim = "impulse_purchase_signals", DISCIPLINE
    rows = [e for e in data.expenses_in_rate_window() if not data.is_essential(e.category_id)]
    if len(rows) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})
    by_day = Counter(e.on for e in rows)
    cluster_days = sum(1 for c in by_day.values() if c >= 3)
    active_days = len(by_day)
    rate = cluster_days / active_days if active_days else 0.0
    score = scoring.clamp_score(100 - rate * 200)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(rate, 3))), score=score, confidence="normal",
        trend="unknown",
        facts={"cluster_rate": round(rate, 3), "cluster_days": cluster_days, "kind": "timing_proxy"},
    )


# --------------------------------------------------------------------------- #
@register(key="savings_forecast_reliability", dimension=SAVINGS, direction=HIGHER_BETTER,
          notification_kinds=(OPPORTUNITY, ACHIEVEMENT))
def savings_forecast_reliability(data: BehaviorData) -> scoring.BehavioralMetric:
    """When the user sets a monthly savings target, how often they actually hit it."""
    key, dim = "savings_forecast_reliability", SAVINGS
    targets = [g for g in data.goals if g.kind == "monthly_target" and g.status == "active"]
    if not targets:
        return scoring.insufficient(key, dim, "no_monthly_target")
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    target = max(g.target_amount for g in targets)
    net = aggregates.net_by_month(data, months)
    evaluated = [m for m in months if any(g.start_date <= _month_cutoff(m) for g in targets)]
    if len(evaluated) < 2:
        return scoring.insufficient(key, dim, "target_too_new", {"evaluated": len(evaluated)})
    hits = sum(1 for m in evaluated if net[m] >= target)
    rate = hits / len(evaluated)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(rate, 3))), score=scoring.clamp_score(rate * 100),
        confidence="normal", trend="unknown",
        facts={"hit_rate": round(rate, 3), "target": str(target), "evaluated": len(evaluated)},
    )


# --------------------------------------------------------------------------- #
@register(key="seasonal_spending_pattern", dimension=LIFESTYLE, direction=DESCRIPTIVE,
          notification_kinds=(REMINDER,))
def seasonal_spending_pattern(data: BehaviorData) -> scoring.BehavioralMetric:
    """Descriptive month-of-year spend index + recurring annual events (needs >=12 mo)."""
    key, dim = "seasonal_spending_pattern", LIFESTYLE
    lm = data.long_monthly
    if len(lm) < _SEASONAL_MIN_MONTHS:
        return scoring.insufficient(key, dim, "needs_more_history", {"months_observed": len(lm)})

    by_moy: dict[int, list[float]] = {}
    for (_y, mo), tot in lm.items():
        by_moy.setdefault(mo, []).append(float(tot))
    moy_avg = {mo: sum(v) / len(v) for mo, v in by_moy.items()}
    overall = sum(moy_avg.values()) / len(moy_avg) if moy_avg else 0.0
    peaks = sorted(mo for mo, a in moy_avg.items() if overall > 0 and a > overall * 1.2)
    strength = (max(moy_avg.values()) / overall) if overall > 0 else 1.0
    events = sorted({p.occasion_type for p in data.planned if p.is_recurring and p.occasion_type})
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(strength, 2))), score=50, confidence="normal",
        trend="flat", label="seasonal_pattern",
        facts={"peak_months": peaks, "index": round(strength, 2),
               "recurring_events": list(events), "months_observed": len(lm)},
    )


# --------------------------------------------------------------------------- #
@register(key="offer_susceptibility_proxy", dimension=DISCIPLINE, direction=DESCRIPTIVE,
          controllable=True, notification_kinds=(OPPORTUNITY,))
def offer_susceptibility_proxy(data: BehaviorData) -> scoring.BehavioralMetric:
    """Offer EXPOSURE (not influence): how often offers appear in logged decisions.
    Always low confidence — true offer influence needs the future outcome log."""
    key, dim = "offer_susceptibility_proxy", DISCIPLINE
    evs = data.decision_events
    if len(evs) < _MIN_DECISIONS:
        return scoring.insufficient(key, dim, "insufficient_decisions", {"decisions": len(evs)})
    offer = sum(1 for e in evs if e.offer_involved)
    rate = offer / len(evs)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(rate, 3))),
        score=scoring.clamp_score(100 - rate * 100), confidence="low", label="exposure_proxy",
        trend="unknown",
        facts={"offer_exposure_rate": round(rate, 3), "decisions": len(evs),
               "offer_decisions": offer, "kind": "exposure_proxy"},
    )
