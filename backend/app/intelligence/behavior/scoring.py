"""Behavioral Intelligence — scoring, aggregation, and profile assembly.

Pure + deterministic. Provides the helpers metric functions use (score
normalisation, trend classification, statistics) and the orchestration that
turns registered metrics into a BehavioralProfile: dimensions -> composite ->
SWOR -> recommendation signals -> advisor views.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.intelligence.behavior import registry
from app.intelligence.behavior.data import BehaviorData
from app.intelligence.behavior.profile import (
    OPPORTUNITY_HIGH,
    OPPORTUNITY_LOW,
    STRONG_SCORE,
    WEAK_SCORE,
    BehavioralDimension,
    BehavioralMetric,
    BehavioralProfile,
    RecommendationSignal,
    SworItem,
)

NEUTRAL_SCORE = 50
_LOW_WEIGHT = 0.3   # confidence weighting in dimension means
_NORMAL_WEIGHT = 1.0
_DEADBAND = 0.05

# Human titles for SWOR statements (presentation only; defaults to humanised key).
TITLES: dict[str, str] = {
    "weekend_overspending": "weekend spending control",
    "salary_day_spending_spike": "post-salary spending control",
    "shopping_spend_share": "shopping spending share",
    "category_concentration": "spending spread across categories",
    "discretionary_spend_ratio": "discretionary spending ratio",
    "recurring_cost_load": "recurring commitment load",
    "budget_session_success_rate": "budget session success",
    "threshold_violation_frequency": "monthly limit discipline",
    "planned_vs_actual_variance": "planning accuracy",
    "average_monthly_surplus": "monthly surplus",
    "spending_stability": "month-to-month spending stability",
    "savings_consistency": "savings consistency",
    "emergency_buffer_stability": "emergency buffer stability",
    "receivable_recovery_rate": "getting lent money back",
    "income_reliability_score": "income reliability",
    "recurring_income_dependency": "recurring income share",
}

# Issue label for recommendation signals (by metric key; default per-direction).
ISSUES: dict[str, str] = {
    "weekend_overspending": "weekend_overspending",
    "salary_day_spending_spike": "post_salary_spike",
    "shopping_spend_share": "shopping_concentration",
    "category_concentration": "category_concentration",
    "discretionary_spend_ratio": "discretionary_pressure",
    "recurring_cost_load": "commitment_pressure",
    "budget_session_success_rate": "budget_overruns",
    "threshold_violation_frequency": "threshold_violations",
    "planned_vs_actual_variance": "planning_inaccuracy",
    "average_monthly_surplus": "low_surplus",
    "spending_stability": "spending_volatility",
    "savings_consistency": "inconsistent_savings",
    "emergency_buffer_stability": "buffer_instability",
    "receivable_recovery_rate": "low_recovery",
    "income_reliability_score": "unreliable_income",
    "recurring_income_dependency": "income_concentration",
}


# --------------------------------------------------------------------------- #
#  Helpers used by metric functions
# --------------------------------------------------------------------------- #
def clamp_score(x: float | Decimal) -> int:
    return max(0, min(100, int(round(float(x)))))


def band_label(score: int) -> str:
    if score >= STRONG_SCORE:
        return "good"
    if score >= WEAK_SCORE:
        return "watch"
    return "concern"


def mean_dec(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / len(values) if values else Decimal("0")


def coefficient_of_variation(values: list[Decimal]) -> Decimal:
    """stdev / mean of a series (0 when fewer than 2 points or zero mean)."""
    if len(values) < 2:
        return Decimal("0")
    floats = [float(v) for v in values]
    avg = statistics.fmean(floats)
    if avg == 0:
        return Decimal("0")
    return Decimal(str(statistics.pstdev(floats) / abs(avg)))


def safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return (numerator / denominator) if denominator and denominator != 0 else None


def classify_trend(recent: Decimal | None, prior: Decimal | None, direction: str) -> str:
    """Compare a recent sub-period vs an earlier one, toward the healthy direction."""
    if recent is None or prior is None:
        return "unknown"
    if direction == registry.DESCRIPTIVE:
        return "flat"
    r, p = float(recent), float(prior)
    if p == 0:
        if abs(r) < 1e-9:
            return "flat"
        better = (direction == registry.HIGHER_BETTER and r > 0) or (direction == registry.LOWER_BETTER and r < 0)
        return "improving" if better else "worsening"
    change = (r - p) / abs(p)
    if abs(change) < _DEADBAND:
        return "flat"
    increased = change > 0
    if direction == registry.HIGHER_BETTER:
        return "improving" if increased else "worsening"
    return "worsening" if increased else "improving"


def metric(
    *,
    key: str,
    dimension: str,
    value: Decimal | None,
    score: int,
    confidence: str,
    trend: str = "unknown",
    label: str | None = None,
    facts: dict[str, Any] | None = None,
) -> BehavioralMetric:
    return BehavioralMetric(
        key=key,
        dimension=dimension,
        value=value,
        score=clamp_score(score),
        label=label or band_label(clamp_score(score)),
        trend=trend,
        confidence=confidence,
        facts=facts or {},
    )


def insufficient(key: str, dimension: str, reason: str, facts: dict[str, Any] | None = None) -> BehavioralMetric:
    """Cold-start / low-data metric: neutral score, explicit reason, low confidence."""
    return BehavioralMetric(
        key=key,
        dimension=dimension,
        value=None,
        score=NEUTRAL_SCORE,
        label=reason,
        trend="unknown",
        confidence="low",
        facts=facts or {},
    )


# --------------------------------------------------------------------------- #
#  Aggregation
# --------------------------------------------------------------------------- #
def _weight(confidence: str) -> float:
    return _NORMAL_WEIGHT if confidence == "normal" else _LOW_WEIGHT


def build_dimensions(metrics: list[BehavioralMetric]) -> dict[str, BehavioralDimension]:
    grouped: dict[str, list[BehavioralMetric]] = defaultdict(list)
    for m in metrics:
        grouped[m.dimension].append(m)

    dims: dict[str, BehavioralDimension] = {}
    for name in registry.DIMENSION_ORDER:
        members = grouped.get(name, [])
        if not members:
            continue
        total_w = sum(_weight(m.confidence) for m in members)
        score = round(sum(m.score * _weight(m.confidence) for m in members) / total_w) if total_w else NEUTRAL_SCORE
        normal = sum(1 for m in members if m.confidence == "normal")
        confidence = "normal" if normal * 2 >= len(members) and normal >= 1 else "low"
        dims[name] = BehavioralDimension(
            name=name,
            score=clamp_score(score),
            confidence=confidence,
            metric_keys=tuple(m.key for m in members),
        )
    return dims


def build_composite(dims: dict[str, BehavioralDimension], metrics: list[BehavioralMetric]) -> tuple[int, str]:
    total_w = sum(registry.DIMENSION_WEIGHTS[name] for name in dims)
    if total_w == 0:
        return NEUTRAL_SCORE, "low"
    score = round(sum(d.score * registry.DIMENSION_WEIGHTS[name] for name, d in dims.items()) / total_w)
    normal = sum(1 for m in metrics if m.confidence == "normal")
    confidence = "normal" if metrics and normal * 2 >= len(metrics) else "low"
    return clamp_score(score), confidence


# --------------------------------------------------------------------------- #
#  Strengths / Weaknesses / Opportunities / Risks
# --------------------------------------------------------------------------- #
def _title(key: str) -> str:
    return TITLES.get(key, key.replace("_", " "))


def build_swor(metrics: list[BehavioralMetric]) -> dict[str, tuple[SworItem, ...]]:
    strengths, weaknesses, opportunities, risks = [], [], [], []
    for m in metrics:
        spec = registry.METRIC_REGISTRY[m.key]
        title = _title(m.key)
        if m.confidence != "normal":
            continue

        def item(statement: str, level: str) -> SworItem:
            return SworItem(m.key, m.dimension, statement, level, m.score, m.trend, m.confidence)

        if m.score >= STRONG_SCORE:
            strengths.append(item(f"Strong {title}", "strong" if m.score >= 85 else "mild"))

        if m.score <= WEAK_SCORE and m.trend != "improving":
            weaknesses.append(item(f"{title.capitalize()} needs attention", "high" if m.score <= 25 else "moderate"))

        if (
            spec.controllable
            and OPPORTUNITY_LOW <= m.score <= OPPORTUNITY_HIGH
            and m.trend in ("flat", "worsening", "unknown")
        ):
            opportunities.append(item(f"Room to improve {title}", "high" if m.score <= 55 else "moderate"))

        if spec.forward_risk and (m.trend == "worsening" or m.score <= WEAK_SCORE):
            level = "high" if (m.trend == "worsening" and m.score <= WEAK_SCORE) else "moderate"
            risks.append(item(f"{title.capitalize()} is trending the wrong way", level))

    return {
        "strengths": tuple(strengths),
        "weaknesses": tuple(weaknesses),
        "opportunities": tuple(opportunities),
        "risks": tuple(risks),
    }


# --------------------------------------------------------------------------- #
#  Recommendation signals (C9)
# --------------------------------------------------------------------------- #
def build_signals(metrics: list[BehavioralMetric], advisor: dict[str, Any]) -> tuple[RecommendationSignal, ...]:
    signals: list[RecommendationSignal] = []
    for m in metrics:
        if m.confidence != "normal" or m.score >= OPPORTUNITY_HIGH:
            continue
        severity = "high" if m.score < WEAK_SCORE else "medium" if m.score < OPPORTUNITY_HIGH else "low"
        signals.append(
            RecommendationSignal(
                key=m.key,
                issue=ISSUES.get(m.key, "below_target"),
                severity=severity,
                impact=(100 - m.score) / 100.0,
                confidence=m.confidence,
                direction=m.trend,
                evidence=dict(m.facts),
            )
        )
    # Per-category overspending signals (the canonical {category, issue, impact} shape).
    for cat in advisor.get("overspending_categories", []):
        impact = float(cat.get("share", 0.0))
        severity = "high" if impact >= 0.30 else "medium" if impact >= 0.15 else "low"
        signals.append(
            RecommendationSignal(
                key=cat["category"],
                issue="overspending",
                severity=severity,
                impact=impact,
                confidence="normal",
                direction=cat.get("direction", "unknown"),
                evidence=cat,
            )
        )
    return tuple(signals)


# --------------------------------------------------------------------------- #
#  Advisor view (C7) — derived directly from data (category-level)
# --------------------------------------------------------------------------- #
def build_advisor_view(data: BehaviorData) -> dict[str, Any]:
    window = data.window
    months = window.complete_months or window.months
    n_months = max(1, len(months))

    # Per-category totals over complete months + recent vs trailing.
    cat_total: dict[Any, Decimal] = defaultdict(lambda: Decimal("0"))
    cat_recent: dict[Any, Decimal] = defaultdict(lambda: Decimal("0"))
    cat_trailing: dict[Any, Decimal] = defaultdict(lambda: Decimal("0"))
    last_month = months[-1] if months else window.current_month
    trailing_months = [m for m in months if m != last_month]
    total_all = Decimal("0")
    for e in data.expenses:
        ym = (e.on.year, e.on.month)
        if ym not in set(months):
            continue
        cat_total[e.category_id] += e.amount
        total_all += e.amount
        if ym == last_month:
            cat_recent[e.category_id] += e.amount
        elif ym in trailing_months:
            cat_trailing[e.category_id] += e.amount

    def cat_name(cid: Any) -> str:
        info = data.categories.get(cid)
        return info.name if info else "Uncategorized"

    overspending, cuttable, low_impact, savings_opps = [], [], [], []
    trailing_n = max(1, len(trailing_months))
    for cid, total in cat_total.items():
        share = float(total / total_all) if total_all > 0 else 0.0
        controllable = not data.is_essential(cid)
        recent = cat_recent.get(cid, Decimal("0"))
        trailing_avg = cat_trailing.get(cid, Decimal("0")) / trailing_n
        rising = trailing_avg > 0 and recent > trailing_avg * Decimal("1.3")
        entry = {
            "category": cat_name(cid),
            "share": round(share, 4),
            "monthly_avg": str((total / n_months).quantize(Decimal("0.01"))),
            "controllable": controllable,
            "direction": "worsening" if rising else "flat",
        }
        if controllable and (rising or share >= 0.20):
            overspending.append(entry)
        if controllable:
            cuttable.append(entry)
            savings_opps.append({**entry, "potential_monthly": entry["monthly_avg"]})
        if controllable and share < 0.05:
            low_impact.append(entry)

    cuttable.sort(key=lambda c: c["share"], reverse=True)
    savings_opps.sort(key=lambda c: c["share"], reverse=True)
    overspending.sort(key=lambda c: c["share"], reverse=True)

    impulse_periods = []
    if data.salary_days:
        impulse_periods.append({"type": "post_salary", "days_after": 3, "salary_days": sorted(data.salary_days)})
    impulse_periods.append({"type": "weekend", "weekdays": [5, 6]})

    return {
        "overspending_categories": overspending[:5],
        "best_categories_to_cut": cuttable[:5],
        "low_impact_categories": low_impact[:5],
        "likely_impulse_periods": impulse_periods,
        "strongest_savings_opportunities": savings_opps[:3],
    }


# --------------------------------------------------------------------------- #
#  Top-level assembly
# --------------------------------------------------------------------------- #
def build_profile_from_data(data: BehaviorData) -> BehavioralProfile:
    if not registry.METRIC_REGISTRY:  # pragma: no cover - guarded by metric import
        raise RuntimeError("No behavioral metrics registered; import app.intelligence.behavior.metrics first")

    metrics = [spec.compute(data) for spec in registry.METRIC_REGISTRY.values()]
    dims = build_dimensions(metrics)
    composite, confidence = build_composite(dims, metrics)
    advisor = build_advisor_view(data)
    swor = build_swor(metrics)
    signals = build_signals(metrics, advisor)

    window = data.window
    return BehavioralProfile(
        today=window.today,
        base_currency=data.base_currency,
        window={
            "rate_days": window.rate_days,
            "buckets": len(window.months),
            "complete_months": len(window.complete_months),
            "month_start": window.month_start.isoformat(),
        },
        composite_score=composite,
        confidence=confidence,
        metrics=tuple(metrics),
        dimensions=dims,
        strengths=swor["strengths"],
        weaknesses=swor["weaknesses"],
        opportunities=swor["opportunities"],
        risks=swor["risks"],
        recommendation_signals=signals,
        advisor=advisor,
    )
