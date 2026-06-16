"""B1.5a Advanced Behavioral metrics — trend-aware, why-money-disappears signals.

Each reuses the shared monthly aggregates + the real trend engine (so they carry
genuine trend_duration_months) and stays cold-start neutral. They answer the
advisor's questions ("why is it harder to save?", "what habit is hurting me most?",
"what should I stop repeating?") and feed B2 / C9 / C7a-2 / future C8.
"""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import aggregates, scoring, trend
from app.intelligence.behavior.data import BehaviorData
from app.intelligence.behavior.registry import (
    DISCIPLINE,
    LIFESTYLE,
    LOWER_BETTER,
    OPPORTUNITY,
    WARNING,
    register,
)

_MIN_MONTHS = 3       # complete months needed for any trend/slope metric
_MIN_ROWS = 20        # expense rows needed for confidence


def _rows_in(data: BehaviorData, months: tuple) -> int:
    allowed = set(months)
    return sum(1 for e in data.expenses if (e.on.year, e.on.month) in allowed)


def _cat_name(data: BehaviorData, cid) -> str:
    info = data.categories.get(cid)
    return info.name if info else "Uncategorized"


# --------------------------------------------------------------------------- #
@register(key="lifestyle_inflation", dimension=LIFESTYLE, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY),
          personality_tags=("experience_seeker", "social_spender"))
def lifestyle_inflation(data: BehaviorData) -> scoring.BehavioralMetric:
    """Discretionary spend relative to income, and whether it's drifting upward."""
    key, dim = "lifestyle_inflation", LIFESTYLE
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    if _rows_in(data, months) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": _rows_in(data, months)})
    ref = aggregates.income_reference(data, months)
    if ref <= 0:
        return scoring.insufficient(key, dim, "no_income_reference")

    disc = aggregates.discretionary_by_month(data, months)
    ratio_map = {m: (disc[m] / ref) for m in months}
    series = trend.series_for_months(ratio_map, months)
    trnd, dur = trend.run_length(series, LOWER_BETTER)
    latest = series[-1]
    level_score = 100 - max(0.0, float(latest) - 0.40) * 150
    penalty = min(30, dur * 8) if trnd == "worsening" else 0
    return scoring.metric(
        key=key, dimension=dim, value=latest.quantize(Decimal("0.001")),
        score=scoring.clamp_score(level_score - penalty), confidence="normal",
        trend=trnd, trend_duration_months=dur,
        facts={"discretionary_to_income": str(latest.quantize(Decimal("0.001"))),
               "monthly_ratios": [str(v.quantize(Decimal("0.001"))) for v in series],
               "income_reference": str(ref)},
    )


# --------------------------------------------------------------------------- #
@register(key="spending_escalation_rate", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, notification_kinds=(WARNING, OPPORTUNITY),
          personality_tags=("impulse_buyer",))
def spending_escalation_rate(data: BehaviorData) -> scoring.BehavioralMetric:
    """Month-over-month growth of discretionary spend (velocity, not level)."""
    key, dim = "spending_escalation_rate", DISCIPLINE
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    if _rows_in(data, months) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": _rows_in(data, months)})

    disc = aggregates.discretionary_by_month(data, months)
    series = trend.series_for_months(disc, months)
    if sum(series, Decimal("0")) <= 0:
        return scoring.insufficient(key, dim, "no_discretionary_spend")
    trnd, dur = trend.run_length(series, LOWER_BETTER)
    prev, cur = float(series[-2]), float(series[-1])
    growth = (cur - prev) / prev if prev > 0 else 0.0
    penalty = min(30, dur * 8) if trnd == "worsening" else 0
    score = scoring.clamp_score(100 - max(0.0, growth) * 200 - penalty)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(str(round(growth, 4))),
        score=score, confidence="normal", trend=trnd, trend_duration_months=dur,
        facts={"recent_mom_growth": round(growth, 4),
               "monthly_totals": [str(v.quantize(Decimal("0.01"))) for v in series]},
    )


# --------------------------------------------------------------------------- #
@register(key="category_volatility", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, notification_kinds=(OPPORTUNITY,))
def category_volatility(data: BehaviorData) -> scoring.BehavioralMetric:
    """How erratic month-to-month spending is within categories (mean CoV)."""
    key, dim = "category_volatility", DISCIPLINE
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})

    by_cat = aggregates.by_category_by_month(data, months)
    covs: list[Decimal] = []
    for _cid, mmap in by_cat.items():
        vals = trend.series_for_months(mmap, months)
        if sum(vals, Decimal("0")) <= 0 or sum(1 for v in vals if v > 0) < 2:
            continue
        covs.append(scoring.coefficient_of_variation(vals))
    if len(covs) < 2:
        return scoring.insufficient(key, dim, "insufficient_data", {"categories": len(covs)})

    mean_cov = scoring.mean_dec(covs)
    score = scoring.clamp_score(100 - max(0.0, float(mean_cov) - 0.40) * 150)
    return scoring.metric(
        key=key, dimension=dim, value=mean_cov.quantize(Decimal("0.001")),
        score=score, confidence="normal", trend="flat",
        facts={"mean_category_cov": str(mean_cov.quantize(Decimal("0.001"))), "categories": len(covs)},
    )


# --------------------------------------------------------------------------- #
@register(key="commitment_pressure", dimension=LIFESTYLE, direction=LOWER_BETTER,
          forward_risk=True, notification_kinds=(WARNING,), personality_tags=("risk_taker",))
def commitment_pressure(data: BehaviorData) -> scoring.BehavioralMetric:
    """Trajectory of recurring commitments vs income (commitment creep + headroom)."""
    key, dim = "commitment_pressure", LIFESTYLE
    if not any(p.is_recurring for p in data.planned):
        return scoring.insufficient(key, dim, "no_commitment_data")
    months = data.window.complete_months
    if len(months) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_history", {"months": len(months)})
    ref = aggregates.income_reference(data, months)
    if ref <= 0:
        return scoring.insufficient(key, dim, "no_income_reference")

    cum = aggregates.cumulative_recurring_by_month(data, months)
    ratio_map = {m: (cum[m] / ref) for m in months}
    series = trend.series_for_months(ratio_map, months)
    trnd, dur = trend.run_length(series, LOWER_BETTER)
    latest = series[-1]
    penalty = min(25, dur * 7) if trnd == "worsening" else 0
    score = scoring.clamp_score(100 - max(0.0, float(latest) - 0.30) * 200 - penalty)
    return scoring.metric(
        key=key, dimension=dim, value=latest.quantize(Decimal("0.001")),
        score=score, confidence="normal", trend=trnd, trend_duration_months=dur,
        facts={"commitment_load": str(latest.quantize(Decimal("0.001"))),
               "headroom": str((Decimal("1") - latest).quantize(Decimal("0.001"))),
               "income_reference": str(ref)},
    )


# --------------------------------------------------------------------------- #
@register(key="upgrade_replacement_behavior", dimension=LIFESTYLE, direction=LOWER_BETTER,
          controllable=True, notification_kinds=(OPPORTUNITY,), personality_tags=("experience_seeker",))
def upgrade_replacement_behavior(data: BehaviorData) -> scoring.BehavioralMetric:
    """Repeat large buys in the same category within a short interval (upgrade/replace proxy)."""
    key, dim = "upgrade_replacement_behavior", LIFESTYLE
    months = set(data.window.months)
    rows = [e for e in data.expenses if (e.on.year, e.on.month) in months and not data.is_essential(e.category_id)]
    if len(rows) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})

    by_cat: dict[object, list] = {}
    for e in rows:
        by_cat.setdefault(e.category_id, []).append(e)

    events = 0
    flagged: list[str] = []
    for cid, es in by_cat.items():
        if len(es) < 2:
            continue
        mean = scoring.mean_dec([x.amount for x in es])
        if mean <= 0:
            continue
        large = sorted((x for x in es if x.amount >= mean * Decimal("1.5")), key=lambda x: x.on)
        clusters = sum(1 for i in range(1, len(large)) if (large[i].on - large[i - 1].on).days <= 90)
        if clusters >= 1:
            events += clusters
            flagged.append(_cat_name(data, cid))

    score = scoring.clamp_score(100 - events * 20)
    return scoring.metric(
        key=key, dimension=dim, value=Decimal(events),
        score=score, confidence="normal", trend="unknown",
        facts={"replacement_events": events, "categories": flagged[:5]},
    )
