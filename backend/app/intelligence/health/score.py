"""C8 — Financial Health Score (pure aggregator over a BehavioralProfile).

Facts explain, scores summarize. C8 creates NO new intelligence and NO financial
math — it re-projects already-computed metric scores into six explainable health
pillars, weighting each metric by confidence (H7) and establishment/stability
(H3). Descriptive metrics (seasonal, offer proxy) are not mapped, so they can
never move the score (H11). Every pillar and the overall carry fact-linked
contributors so the score is always decomposable to reasons.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.intelligence.behavior import registry
from app.intelligence.behavior.profile import STRONG_SCORE, WEAK_SCORE, BehavioralMetric, BehavioralProfile
from app.intelligence.behavior.scoring import _title as _metric_title

SCHEMA_VERSION = 1

# --- pillars (H1) ----------------------------------------------------------- #
CASHFLOW, RESILIENCE, DISCIPLINE, STABILITY, PLANNING, RISK_AWARENESS = (
    "cashflow", "resilience", "discipline", "stability", "planning", "risk_awareness"
)
PILLAR_ORDER = (CASHFLOW, RESILIENCE, DISCIPLINE, STABILITY, PLANNING, RISK_AWARENESS)
PILLAR_LABELS = {
    CASHFLOW: "Cashflow", RESILIENCE: "Resilience", DISCIPLINE: "Discipline",
    STABILITY: "Stability", PLANNING: "Planning", RISK_AWARENESS: "Risk Awareness",
}
PILLAR_WEIGHTS = {
    CASHFLOW: 0.22, RESILIENCE: 0.20, DISCIPLINE: 0.18, STABILITY: 0.16, PLANNING: 0.14, RISK_AWARENESS: 0.10,
}

# --- metric -> pillar (H2; each scoring metric maps to exactly one pillar) --- #
METRIC_PILLAR: dict[str, str] = {
    # Discipline
    "weekend_overspending": DISCIPLINE, "salary_day_spending_spike": DISCIPLINE,
    "shopping_spend_share": DISCIPLINE, "discretionary_spend_ratio": DISCIPLINE,
    "lifestyle_inflation": DISCIPLINE, "spending_escalation_rate": DISCIPLINE,
    "upgrade_replacement_behavior": DISCIPLINE, "payday_decay": DISCIPLINE,
    "impulse_purchase_signals": DISCIPLINE,
    # Stability
    "spending_stability": STABILITY, "category_concentration": STABILITY, "category_volatility": STABILITY,
    # Planning
    "planned_vs_actual_variance": PLANNING, "budget_session_success_rate": PLANNING,
    "planned_vs_actual_drift": PLANNING, "expense_prediction_accuracy": PLANNING,
    "savings_forecast_reliability": PLANNING,
    # Resilience
    "emergency_buffer_stability": RESILIENCE, "financial_stress_index": RESILIENCE,
    "savings_recovery_rate": RESILIENCE, "spending_recovery_speed": RESILIENCE,
    # Cashflow
    "average_monthly_surplus": CASHFLOW, "savings_consistency": CASHFLOW,
    "threshold_violation_frequency": CASHFLOW, "recurring_cost_load": CASHFLOW, "commitment_pressure": CASHFLOW,
    # Risk Awareness (recurring_income_dependency is DESCRIPTIVE -> excluded, H11)
    "income_reliability_score": RISK_AWARENESS, "income_dependency_concentration": RISK_AWARENESS,
    "receivable_recovery_rate": RISK_AWARENESS, "goal_interference_rate": RISK_AWARENESS,
}

_EST_BASE, _EST_STEP, _EST_CAP = 0.6, 0.1, 4   # establishment multiplier 0.6 .. 1.0


def _conf_weight(confidence: str) -> float:
    return 1.0 if confidence == "normal" else 0.3


def _establishment(metric: BehavioralMetric, complete_months: int) -> float:
    """H3: sustained patterns count more than new ones (trend_duration, else window)."""
    months = metric.trend_duration_months if metric.trend_duration_months is not None else complete_months
    return _EST_BASE + _EST_STEP * max(0, min(_EST_CAP, months))


def _state(score: int) -> str:
    return "strong" if score >= STRONG_SCORE else "fair" if score >= WEAK_SCORE else "weak"


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class HealthPillar:
    key: str
    label: str
    score: int
    confidence: str
    state: str
    trend: str
    trend_duration_months: int | None
    contributors: tuple[dict[str, Any], ...]
    warning_eligible: bool
    achievement_eligible: bool
    reminder_eligible: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "label": self.label, "score": self.score, "confidence": self.confidence,
            "state": self.state, "trend": self.trend, "trend_duration_months": self.trend_duration_months,
            "contributors": list(self.contributors),
            "warning_eligible": self.warning_eligible, "achievement_eligible": self.achievement_eligible,
            "reminder_eligible": self.reminder_eligible,
        }


@dataclass(frozen=True)
class HealthScore:
    overall_score: int
    overall_confidence: str
    overall_state: str
    pillars: tuple[HealthPillar, ...]
    top_strengths: tuple[str, ...]
    top_weaknesses: tuple[str, ...]
    biggest_contributor: dict[str, Any] | None
    biggest_drag: dict[str, Any] | None
    improving_area: str | None
    worsening_area: str | None
    contributor_index: dict[str, Any]
    facts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score, "overall_confidence": self.overall_confidence,
            "overall_state": self.overall_state, "schema_version": SCHEMA_VERSION,
            "pillars": [p.as_dict() for p in self.pillars],
            "top_strengths": list(self.top_strengths), "top_weaknesses": list(self.top_weaknesses),
            "biggest_contributor": self.biggest_contributor, "biggest_drag": self.biggest_drag,
            "improving_area": self.improving_area, "worsening_area": self.worsening_area,
            "contributor_index": self.contributor_index, "facts": self.facts,
        }


def _reminder_eligible(members: list[BehavioralMetric]) -> bool:
    return any(registry.REMINDER in registry.METRIC_REGISTRY[m.key].notification_kinds for m in members)


def _build_pillar(key: str, members: list[BehavioralMetric], complete_months: int) -> HealthPillar:
    label = PILLAR_LABELS[key]
    weighted = [(m, _conf_weight(m.confidence) * _establishment(m, complete_months)) for m in members]
    total_w = sum(w for _, w in weighted)
    if not members or total_w == 0:
        return HealthPillar(key, label, 50, "low", "fair", "unknown", None, (), False, False,
                            _reminder_eligible(members))

    score = round(sum(m.score * w for m, w in weighted) / total_w)
    normal = sum(1 for m in members if m.confidence == "normal")
    confidence = "normal" if (normal * 2 >= len(members) and normal >= 1) else "low"
    contributors = tuple(sorted(
        ({"metric_key": m.key, "statement": _metric_title(m.key), "score": m.score, "trend": m.trend,
          "trend_duration_months": m.trend_duration_months, "confidence": m.confidence,
          "contribution": round((m.score - 50) * w, 2)} for m, w in weighted),
        key=lambda c: abs(c["contribution"]), reverse=True))

    worsening = [m for m in members if m.confidence == "normal" and m.trend == "worsening"]
    improving = [m for m in members if m.confidence == "normal" and m.trend == "improving"]
    if worsening:
        lead = max(worsening, key=lambda m: (m.trend_duration_months or 0))
        trend, dur = "worsening", lead.trend_duration_months
    elif improving:
        lead = max(improving, key=lambda m: (m.trend_duration_months or 0))
        trend, dur = "improving", lead.trend_duration_months
    else:
        trend, dur = "flat", None

    state = _state(score)
    established = complete_months >= 4 or any((m.trend_duration_months or 0) >= 4 for m in members)
    warning = confidence == "normal" and (state == "weak" or (trend == "worsening" and (dur or 0) >= 2))
    achievement = confidence == "normal" and state == "strong" and trend in ("flat", "improving") and established
    return HealthPillar(key, label, score, confidence, state, trend, dur, contributors,
                        warning, achievement, _reminder_eligible(members))


def build_health_score(profile: BehavioralProfile) -> HealthScore:
    complete_months = int(profile.window.get("complete_months", 0))
    grouped: dict[str, list[BehavioralMetric]] = defaultdict(list)
    for m in profile.metrics:
        pillar = METRIC_PILLAR.get(m.key)   # descriptive metrics absent -> excluded (H11)
        if pillar:
            grouped[pillar].append(m)

    pillars = {p: _build_pillar(p, grouped.get(p, []), complete_months) for p in PILLAR_ORDER}
    included = [p for p in PILLAR_ORDER if any(mm.confidence == "normal" for mm in grouped.get(p, []))]
    if not included:
        overall, oconf = 50, "low"
    else:
        tw = sum(PILLAR_WEIGHTS[p] for p in included)
        overall = round(sum(pillars[p].score * PILLAR_WEIGHTS[p] for p in included) / tw)
        normal_pillars = sum(1 for p in included if pillars[p].confidence == "normal")
        oconf = "normal" if normal_pillars * 2 >= len(PILLAR_ORDER) else "low"

    # biggest contributor / drag (fact-linked) across all pillars
    all_c = [{**c, "pillar": p} for p in PILLAR_ORDER for c in pillars[p].contributors]
    positives = [c for c in all_c if c["contribution"] > 0]
    negatives = [c for c in all_c if c["contribution"] < 0]
    biggest_contributor = max(positives, key=lambda c: c["contribution"]) if positives else None
    biggest_drag = min(negatives, key=lambda c: c["contribution"]) if negatives else None
    worsening_area = next((p for p in PILLAR_ORDER if pillars[p].trend == "worsening"), None)
    improving_area = next((p for p in PILLAR_ORDER if pillars[p].trend == "improving"), None)

    contributor_index = {
        m.key: {"pillar": METRIC_PILLAR[m.key], "below_pillar": m.score < pillars[METRIC_PILLAR[m.key]].score}
        for m in profile.metrics if m.key in METRIC_PILLAR and m.confidence == "normal"
    }

    return HealthScore(
        overall_score=overall, overall_confidence=oconf, overall_state=_state(overall),
        pillars=tuple(pillars[p] for p in PILLAR_ORDER),
        top_strengths=tuple(s.statement for s in profile.strengths[:3]),
        top_weaknesses=tuple(s.statement for s in profile.weaknesses[:3]),
        biggest_contributor=biggest_contributor, biggest_drag=biggest_drag,
        improving_area=improving_area, worsening_area=worsening_area,
        contributor_index=contributor_index,
        facts={"root_cause": (profile.advisor or {}).get("root_cause"), "schema_version": SCHEMA_VERSION},
    )
