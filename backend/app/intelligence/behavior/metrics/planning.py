"""Planning Adherence metrics."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import scoring
from app.intelligence.behavior.data import BehaviorData, SessionRow, monthly_expense_totals
from app.intelligence.behavior.registry import HIGHER_BETTER, LOWER_BETTER, PLANNING, register
from app.models.enums import PlannedExpenseStatus

_MIN_SESSIONS = 3
_MIN_MONTHS = 3
_MIN_PLANNED = 3


@register(key="budget_session_success_rate", dimension=PLANNING, direction=HIGHER_BETTER,
          controllable=True, personality_tags=("financial_planner",))
def budget_session_success_rate(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "budget_session_success_rate", PLANNING
    sessions = list(data.sessions)
    if len(sessions) < _MIN_SESSIONS:
        return scoring.insufficient(key, dim, "insufficient_sessions", {"completed": len(sessions)})

    def rate(items: list[SessionRow]) -> Decimal | None:
        if not items:
            return None
        under = sum(1 for s in items if s.spent <= s.budget)
        return Decimal(under) / Decimal(len(items))

    overall = rate(sessions) or Decimal("0")
    dated = sorted((s for s in sessions if s.ended_on), key=lambda s: s.ended_on)  # type: ignore[arg-type]
    if len(dated) >= 4:
        half = len(dated) // 2
        prior = rate(dated[:half])
        recent = rate(dated[half:])
    else:
        recent = prior = None
    return scoring.metric(
        key=key, dimension=dim, value=overall.quantize(Decimal("0.001")),
        score=scoring.clamp_score(float(overall) * 100), confidence="normal",
        trend=scoring.classify_trend(recent, prior, HIGHER_BETTER),
        facts={"completed": len(sessions), "under_budget": sum(1 for s in sessions if s.spent <= s.budget),
               "success_rate": str(overall.quantize(Decimal("0.001")))},
    )


@register(key="threshold_violation_frequency", dimension=PLANNING, direction=LOWER_BETTER,
          controllable=True, forward_risk=True, personality_tags=("financial_planner", "risk_taker"))
def threshold_violation_frequency(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "threshold_violation_frequency", PLANNING
    threshold = data.monthly_threshold
    if not threshold or threshold <= 0:
        return scoring.insufficient(key, dim, "no_threshold")
    complete = data.window.complete_months
    if len(complete) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"complete_months": len(complete)})

    totals = monthly_expense_totals(data, complete)
    active = [ym for ym in complete if totals[ym] > 0]  # only judge months with recorded spend
    if len(active) < _MIN_MONTHS:
        return scoring.insufficient(key, dim, "insufficient_data", {"active_months": len(active)})

    violated = [ym for ym in active if totals[ym] > threshold]
    rate = Decimal(len(violated)) / Decimal(len(active))
    score = (1 - float(rate)) * 100

    last = active[-1]
    recent = Decimal("1") if totals[last] > threshold else Decimal("0")
    earlier = active[:-1]
    prior = (Decimal(sum(1 for ym in earlier if totals[ym] > threshold)) / Decimal(len(earlier))) if earlier else None
    return scoring.metric(
        key=key, dimension=dim, value=rate.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"threshold": str(threshold), "months_observed": len(active),
               "months_violated": len(violated), "violation_rate": str(rate.quantize(Decimal("0.001")))},
    )


@register(key="planned_vs_actual_variance", dimension=PLANNING, direction=LOWER_BETTER,
          controllable=True, personality_tags=("financial_planner",))
def planned_vs_actual_variance(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "planned_vs_actual_variance", PLANNING
    today = data.window.today
    # Actual spend per day (proxy: same-day expenses; exact link is future work).
    spend_on: dict[object, Decimal] = {}
    for e in data.expenses:
        spend_on[e.on] = spend_on.get(e.on, Decimal("0")) + e.amount

    variances: list[Decimal] = []
    for p in data.planned:
        if p.planned_date > today or p.status != PlannedExpenseStatus.completed.value or p.amount <= 0:
            continue
        actual = spend_on.get(p.planned_date, Decimal("0"))
        variances.append(abs(actual - p.amount) / p.amount)

    if len(variances) < _MIN_PLANNED:
        return scoring.insufficient(key, dim, "insufficient_data", {"matched": len(variances)})

    mean_var = scoring.mean_dec(variances)
    score = 100 - float(mean_var) * 100
    return scoring.metric(
        key=key, dimension=dim, value=mean_var.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend="unknown",
        facts={"matched_events": len(variances), "mean_abs_pct_variance": str(mean_var.quantize(Decimal("0.001")))},
    )
