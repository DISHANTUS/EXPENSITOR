"""Behavioral Intelligence — scoring, aggregation, and profile assembly.

Pure + deterministic. Provides the helpers metric functions use (score
normalisation, trend classification, statistics) and the orchestration that
turns registered metrics into a BehavioralProfile: dimensions -> composite ->
SWOR -> recommendation signals -> advisor views.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from app.intelligence.behavior import aggregates, registry
from app.intelligence.behavior.aggregates import net_by_month
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
    # B1.5a
    "lifestyle_inflation": "lifestyle inflation",
    "spending_escalation_rate": "spending escalation",
    "category_volatility": "category spending stability",
    "commitment_pressure": "recurring commitment trajectory",
    "upgrade_replacement_behavior": "upgrade & replacement habits",
    # B1.5b
    "financial_stress_index": "financial stress",
    "goal_interference_rate": "goal interference",
    "savings_recovery_rate": "savings recovery",
    "spending_recovery_speed": "spending recovery",
    "income_dependency_concentration": "income concentration",
    # B1.5c
    "payday_decay": "post-payday spending pace",
    "planned_vs_actual_drift": "planning execution",
    "expense_prediction_accuracy": "spending predictability",
    "impulse_purchase_signals": "impulse control",
    "savings_forecast_reliability": "savings target reliability",
    "seasonal_spending_pattern": "seasonal spending",
    "offer_susceptibility_proxy": "offer exposure",
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
    # B1.5a
    "lifestyle_inflation": "lifestyle_inflation",
    "spending_escalation_rate": "spending_escalation",
    "category_volatility": "category_volatility",
    "commitment_pressure": "commitment_pressure",
    "upgrade_replacement_behavior": "frequent_upgrades",
    # B1.5b
    "financial_stress_index": "financial_stress",
    "goal_interference_rate": "goal_interference",
    "savings_recovery_rate": "slow_savings_recovery",
    "spending_recovery_speed": "slow_spending_recovery",
    "income_dependency_concentration": "income_concentration",
    # B1.5c
    "payday_decay": "payday_front_loading",
    "planned_vs_actual_drift": "planning_drift",
    "expense_prediction_accuracy": "unpredictable_spending",
    "impulse_purchase_signals": "impulse_clusters",
    "savings_forecast_reliability": "missed_targets",
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
    trend_duration_months: int | None = None,
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
        trend_duration_months=trend_duration_months,
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


_PERSISTENT_MONTHS = 3  # R1: a trend held this long is treated as persistent


def build_swor(metrics: list[BehavioralMetric]) -> dict[str, tuple[SworItem, ...]]:
    strengths, weaknesses, opportunities, risks = [], [], [], []
    for m in metrics:
        spec = registry.METRIC_REGISTRY[m.key]
        title = _title(m.key)
        if m.confidence != "normal":
            continue
        dur = m.trend_duration_months or 0
        persistent = m.trend == "worsening" and dur >= _PERSISTENT_MONTHS

        def item(statement: str, level: str) -> SworItem:
            return SworItem(m.key, m.dimension, statement, level, m.score, m.trend, m.confidence, m.trend_duration_months)

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
            # R1: a long-running deterioration is high even if the score isn't yet low.
            level = "high" if ((m.trend == "worsening" and m.score <= WEAK_SCORE) or persistent) else "moderate"
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
        # R1: a persistent (multi-month) deterioration ranks above a one-off dip.
        dur = m.trend_duration_months or 0
        persistence = min(0.15, 0.03 * dur) if m.trend == "worsening" else 0.0
        impact = min(1.0, (100 - m.score) / 100.0 + persistence)
        severity = "high" if m.score < WEAK_SCORE else "medium" if m.score < OPPORTUNITY_HIGH else "low"
        if m.trend == "worsening" and dur >= _PERSISTENT_MONTHS and severity == "medium":
            severity = "high"
        signals.append(
            RecommendationSignal(
                key=m.key,
                issue=ISSUES.get(m.key, "below_target"),
                severity=severity,
                impact=impact,
                confidence=m.confidence,
                direction=m.trend,
                evidence={**dict(m.facts), "trend_duration_months": m.trend_duration_months},
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
#  Root-cause hierarchy (R2) — one synthesized "biggest pressure" statement
# --------------------------------------------------------------------------- #
# Ranked candidate causes for a savings shortfall (most upstream first). Filtered
# to whatever is registered + normal-confidence, so B1.5b/c metrics slot in here
# without changing this code.
_ROOT_CAUSE_ORDER = (
    "financial_stress_index",
    "goal_interference_rate",
    "lifestyle_inflation",
    "spending_escalation_rate",
    "planned_vs_actual_drift",
    "payday_decay",
    "savings_recovery_rate",
    "spending_recovery_speed",
    "savings_forecast_reliability",
    "commitment_pressure",
    "income_dependency_concentration",
    "impulse_purchase_signals",
    "category_volatility",
    "discretionary_spend_ratio",
    "recurring_cost_load",
)
_CAUSE_PHRASE = {
    "lifestyle_inflation": "rising discretionary spending",
    "spending_escalation_rate": "spending climbing month over month",
    "goal_interference_rate": "spending interfering with your goals",
    "financial_stress_index": "tightening cash flow",
    "savings_recovery_rate": "slow recovery from savings setbacks",
    "spending_recovery_speed": "slow recovery after spending spikes",
    "income_dependency_concentration": "reliance on a single income source",
    "commitment_pressure": "growing recurring commitments",
    "planned_vs_actual_drift": "plans not matching actual spending",
    "payday_decay": "money spent too fast after payday",
    "savings_forecast_reliability": "savings targets being missed",
    "impulse_purchase_signals": "clustered impulse spending",
    "category_volatility": "erratic category spending",
    "discretionary_spend_ratio": "a high discretionary share",
    "recurring_cost_load": "a heavy recurring-commitment load",
}
_TREND_WORD = {"worsening": "increasing", "improving": "improving", "flat": "steady", "unknown": "forming"}


def build_root_cause(metrics: list[BehavioralMetric]) -> dict[str, Any] | None:
    by_key = {m.key: m for m in metrics}
    scored: list[tuple[float, BehavioralMetric]] = []
    for key in _ROOT_CAUSE_ORDER:
        m = by_key.get(key)
        if m is None or m.confidence != "normal":
            continue
        if not (m.score <= OPPORTUNITY_HIGH or m.trend == "worsening"):
            continue
        dur = m.trend_duration_months or 0
        weight = (100 - m.score) / 100.0 + (0.05 * dur if m.trend == "worsening" else 0.0)
        scored.append((weight, m))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0], reverse=True)
    primary = scored[0][1]
    phrase = _CAUSE_PHRASE.get(primary.key, _title(primary.key))
    dur = primary.trend_duration_months or 0
    if primary.trend == "worsening" and dur >= 1:
        tail = f", which has been {_TREND_WORD['worsening']} for {dur} month{'s' if dur != 1 else ''}"
    else:
        tail = ""
    statement = f"The biggest pressure on your finances right now is {phrase}{tail}."
    return {
        "primary_metric": primary.key,
        "statement": statement,
        "contributors": [m.key for _, m in scored[1:4]],
    }


# --------------------------------------------------------------------------- #
#  Goal Sacrifice (S12) + recovery personality (S4 / S11)
# --------------------------------------------------------------------------- #
def build_goal_sacrifice(data: BehaviorData) -> dict[str, Any] | None:
    """Detect achieving one goal at the cost of another: the shared savings pool
    funds the higher-pace goal(s) and leaves the rest behind."""
    active = [g for g in data.goals if g.status == "active"]
    months = data.window.complete_months
    if len(active) < 2 or len(months) < 3:
        return None
    net = net_by_month(data, months)
    net_rate = mean_dec([net[m] for m in months])
    if net_rate <= 0:
        return None  # a global shortfall, not a sacrifice between goals

    paced: list[tuple[Any, Decimal]] = []
    for g in active:
        if g.kind == "monthly_target":
            paced.append((g, g.target_amount))
        elif g.target_date is not None:
            months_left = max(1, (g.target_date.year - data.today.year) * 12 + (g.target_date.month - data.today.month))
            paced.append((g, g.target_amount / months_left))
    if len(paced) < 2:
        return None

    paced.sort(key=lambda x: x[1], reverse=True)
    cumulative = Decimal("0")
    funded, sacrificed = [], []
    for g, req in paced:
        if cumulative + req <= net_rate:
            cumulative += req
            funded.append(g)
        else:
            sacrificed.append(g)
    if not funded or not sacrificed:
        return None
    primary, behind = funded[0], sacrificed[0]
    return {
        "consuming_goal": primary.name,
        "sacrificed_goals": [g.name for g in sacrificed],
        "statement": (f"Most of your available savings are going toward {primary.name}, "
                      f"slowing progress on {behind.name}."),
    }


def _mean_recovery(metrics_by_key: dict, key: str) -> float | None:
    m = metrics_by_key.get(key)
    if m is None or m.confidence != "normal":
        return None
    return m.facts.get("mean_recovery_months")


def build_recovery_profile(metrics_by_key: dict) -> str | None:
    """S4: fast | average | slow from actual recovery history."""
    speeds = [s for s in (_mean_recovery(metrics_by_key, "savings_recovery_rate"),
                          _mean_recovery(metrics_by_key, "spending_recovery_speed")) if s is not None]
    if not speeds:
        return None
    avg = sum(speeds) / len(speeds)
    return "fast" if avg <= 1.0 else "average" if avg <= 2.0 else "slow"


def build_stress_recovery_profile(metrics_by_key: dict, recovery_profile: str | None) -> str | None:
    """S11: how quickly the user recovers from stress (fast | average | slow | persistent)."""
    stress = metrics_by_key.get("financial_stress_index")
    if stress is None or stress.confidence != "normal":
        return None
    persistent = stress.trend == "worsening" and (stress.trend_duration_months or 0) >= 4
    if persistent and recovery_profile in (None, "slow"):
        return "persistent"
    if recovery_profile in ("fast", "average", "slow"):
        return recovery_profile
    return "persistent" if persistent else "average"


# --------------------------------------------------------------------------- #
#  Budget Recovery Confidence (B1.5c) — derived from B1.5b recovery metrics
# --------------------------------------------------------------------------- #
def build_budget_recovery_confidence(metrics_by_key: dict) -> dict[str, Any] | None:
    speeds = [s for s in (_mean_recovery(metrics_by_key, "savings_recovery_rate"),
                          _mean_recovery(metrics_by_key, "spending_recovery_speed")) if s is not None]
    if not speeds:
        return None
    avg = sum(speeds) / len(speeds)
    n = max(1, round(avg))
    phrase = "within about a month" if n <= 1 else f"in about {n} months"
    return {"mean_recovery_months": round(avg, 2),
            "statement": f"You usually recover from overspending {phrase}."}


# --------------------------------------------------------------------------- #
#  Behavioral Memory Signals (B1.5c) — read-only derived facts (NOT preferences)
# --------------------------------------------------------------------------- #
_DESCRIPTIVE_MEMORY = ("seasonal_spending_pattern", "offer_susceptibility_proxy")


def _months_ago_iso(today: date, n: int) -> str:
    idx = today.month - 1 - n
    return date(today.year + (idx // 12), idx % 12 + 1, 1).isoformat()


def _memory_signal_text(key: str, m: BehavioralMetric) -> str | None:
    low = m.score <= OPPORTUNITY_HIGH
    worse = m.trend == "worsening"
    presence = {
        "weekend_overspending": "Usually spends more on weekends",
        "salary_day_spending_spike": "Usually spends more right after payday",
        "payday_decay": "Tends to spend quickly after payday",
        "category_volatility": "Category spending is uneven month to month",
        "impulse_purchase_signals": "Makes clustered, unplanned purchases",
        "financial_stress_index": "Has been under financial pressure",
        "goal_interference_rate": "Spending often interferes with goals",
        "planned_vs_actual_drift": "Tends to spend more than planned",
    }
    if key in presence and low:
        return presence[key]
    if key in ("lifestyle_inflation", "spending_escalation_rate", "commitment_pressure") and (low or worse):
        return {"lifestyle_inflation": "Discretionary spending has been creeping up",
                "spending_escalation_rate": "Spending has been climbing month over month",
                "commitment_pressure": "Recurring commitments have been growing"}[key]
    hi_lo = {
        "savings_recovery_rate": ("Usually recovers quickly after a savings dip",
                                  "Slow to recover after a savings dip"),
        "spending_recovery_speed": ("Usually returns to normal quickly after a spending spike",
                                    "Slow to return to normal after a spending spike"),
        "expense_prediction_accuracy": ("Spending is highly predictable", "Spending is hard to predict"),
        "savings_forecast_reliability": ("Usually meets monthly savings targets",
                                         "Often falls short of monthly savings targets"),
    }
    if key in hi_lo:
        if m.score >= STRONG_SCORE:
            return hi_lo[key][0]
        if m.score <= WEAK_SCORE:
            return hi_lo[key][1]
        return None
    if key == "seasonal_spending_pattern" and (m.facts.get("peak_months") or []):
        return "Tends to spend more during certain months of the year"
    if key == "offer_susceptibility_proxy" and m.facts.get("offer_exposure_rate", 0) >= 0.4:
        return "Offers and discounts appear in many recent decisions"
    return None


def _memory_confidence(m: BehavioralMetric, dur: int | None) -> str:
    if m.confidence != "normal":
        return "low"
    return "high" if (dur or 0) >= 4 else "normal"


def _memory_stability(m: BehavioralMetric, dur: int | None) -> str:
    if m.trend == "improving":
        return "changing"
    if m.trend == "worsening":
        return "stable" if (dur or 0) >= 4 else "forming"
    return "stable"


def build_behavioral_memory(metrics_by_key: dict, today: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, m in metrics_by_key.items():
        if m.confidence != "normal" and key not in _DESCRIPTIVE_MEMORY:
            continue
        text = _memory_signal_text(key, m)
        if not text:
            continue
        dur = m.trend_duration_months
        out.append({
            "signal": text, "evidence_metric": key, "confidence": _memory_confidence(m, dur),
            "first_observed": _months_ago_iso(today, dur) if dur else None,
            "trend": m.trend, "trend_duration_months": dur, "stability": _memory_stability(m, dur),
        })
    rank_c = {"high": 0, "normal": 1, "low": 2}
    rank_s = {"stable": 0, "forming": 1, "changing": 2}
    out.sort(key=lambda s: (rank_c[s["confidence"]], rank_s.get(s["stability"], 3)))
    return out


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
    # DESCRIPTIVE metrics (seasonal, offer-exposure proxy) are CONTEXT only — excluded
    # from dimensions/composite/SWOR/signals so they never move the health score (R5);
    # they remain in metrics/to_facts/advisor_view/behavioral_memory.
    scoring_metrics = [m for m in metrics if registry.METRIC_REGISTRY[m.key].direction != registry.DESCRIPTIVE]
    dims = build_dimensions(scoring_metrics)
    composite, confidence = build_composite(dims, scoring_metrics)
    advisor = build_advisor_view(data)
    # R2: synthesized root cause; R4: which notifications each metric can generate.
    root_cause = build_root_cause(scoring_metrics)
    if root_cause is not None:
        advisor["root_cause"] = root_cause
    advisor["notification_kinds"] = {
        m.key: list(registry.METRIC_REGISTRY[m.key].notification_kinds)
        for m in metrics if registry.METRIC_REGISTRY[m.key].notification_kinds
    }
    # B1.5b: goal sacrifice (S12) + recovery personalities (S4 / S11).
    by_key = {m.key: m for m in metrics}
    sacrifice = build_goal_sacrifice(data)
    if sacrifice is not None:
        advisor["goal_sacrifice"] = sacrifice
    recovery_profile = build_recovery_profile(by_key)
    if recovery_profile is not None:
        advisor["recovery_profile"] = recovery_profile
    stress_recovery = build_stress_recovery_profile(by_key, recovery_profile)
    if stress_recovery is not None:
        advisor["stress_recovery_profile"] = stress_recovery
    # B1.5c: budget recovery confidence + behavioral memory signals.
    brc = build_budget_recovery_confidence(by_key)
    if brc is not None:
        advisor["budget_recovery_confidence"] = brc
    advisor["behavioral_memory"] = build_behavioral_memory(by_key, data.today)
    swor = build_swor(scoring_metrics)
    signals = build_signals(scoring_metrics, advisor)

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
