"""Financial Decision Engine — orchestrator (C7a, pure, structured-only).

Builds the attribute vector, generates constraint-respecting strategies, scores
each against the existing engines (affordability/guidance/risk/consequence), and
returns a structured DecisionResult. NO prose — the Advisor layer renders that.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date
from decimal import Decimal

from app.intelligence.decision import funding, strategies
from app.intelligence.decision.attributes import DecisionAttributes, classify
from app.intelligence.decision.request import DecisionRequest
from app.intelligence.decision.result import (
    DecisionResult,
    DecisionStrategy,
    ImpactSummary,
    StrategyTradeoffs,
)
from app.intelligence.decision.strategies import StrategyPlan
from app.intelligence.projection import affordability, dependency, guidance, risk
from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario

_RISK_RANK = {"none": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
_IMPACT_PENALTY = {"none": 0, "minor": 5, "moderate": 15, "significant": 30}

_GENERATORS = (
    strategies.plan_buy_now,
    strategies.plan_use_savings,
    strategies.plan_wait_for_income,
    strategies.plan_reduce_discretionary,
    strategies.plan_split_into_stages,
    strategies.plan_move_date,
)


def _augment(scenario: Scenario, amount: Decimal, when: date) -> tuple[Scenario, uuid.UUID]:
    overdue = when < scenario.today
    effective = scenario.today if overdue else when
    days_overdue = (scenario.today - when).days if overdue else 0
    oid = uuid.uuid4()
    extra = OutflowEvent(effective, amount, "hypothetical", oid, overdue, days_overdue)
    horizon = max(scenario.horizon, effective)
    return dataclasses.replace(scenario, outflows=scenario.outflows + (extra,), horizon=horizon), oid


def _impact_level(safe_before: Decimal, safe_after: Decimal, financial: str, risk_before: str, risk_after: str) -> str:
    if safe_before > 0:
        drop = (safe_before - safe_after) / safe_before
    else:
        drop = Decimal("0") if safe_after >= safe_before else Decimal("1")
    if financial == "significant" or drop >= Decimal("0.30") or risk_after in ("high", "critical"):
        return "significant"
    risk_worsened = _RISK_RANK[risk_after] > _RISK_RANK[risk_before]
    if financial == "moderate" or drop >= Decimal("0.10") or risk_worsened:
        return "moderate"
    if drop > 0 or financial == "minor":
        return "minor"
    return "none"


def _soft_match(plan: StrategyPlan, request: DecisionRequest) -> bool:
    c = request.constraints
    if plan.kind == "use_savings":
        return c.willing_to_use_savings
    if plan.kind in ("wait_for_income", "move_date", "split_into_stages"):
        return c.willing_to_delay
    if plan.kind == "reduce_discretionary":
        return c.willing_to_reduce_spending
    return False


def _score(feasible: bool, impact_level: str, days_delay: int, risk_before: str, risk_after: str,
           soft_match: bool, floor_preserved: bool) -> int:
    if not feasible:
        return 5
    s = 70 - _IMPACT_PENALTY[impact_level] - min(20, int(days_delay * 0.5))
    if _RISK_RANK[risk_after] > _RISK_RANK[risk_before]:
        s -= 15
    if floor_preserved:
        s += 10
    if soft_match:
        s += 10
    return max(0, min(100, s))


def _tradeoffs(plan: StrategyPlan, *, days_delay: int, safe_before: Decimal, safe_after: Decimal,
               floor_preserved: bool, expected_ok: bool) -> StrategyTradeoffs:
    harder, easier, delayed, unaffected = [], [], [], []
    if safe_after < safe_before:
        harder.append("Tighter daily budget until your next income.")
    if days_delay > 0:
        delayed.append("The purchase happens later.")
    if floor_preserved:
        easier.append("Your emergency reserve stays intact.")
    if expected_ok:
        unaffected.append("Your other plans stay covered.")
    return StrategyTradeoffs(tuple(harder), tuple(easier), tuple(delayed), tuple(unaffected))


def _days_until_recovery(scenario: Scenario, amount: Decimal, when: date) -> int | None:
    augmented, _ = _augment(scenario, amount, when)
    pre = scenario.current_balance
    for point in project(augmented, ScenarioMode.expected):
        if point.date > scenario.today and point.balance >= pre:
            return (point.date - scenario.today).days
    return None


def _enrich(plan: StrategyPlan, request: DecisionRequest, attrs: DecisionAttributes, scenario: Scenario,
            base_safe_daily: Decimal, base_risk_level: str) -> DecisionStrategy:
    amount = request.amount_base
    aff = affordability.evaluate(scenario, amount, plan.purchase_date)
    augmented, _ = _augment(scenario, amount, plan.purchase_date)
    after_guidance = guidance.build(augmented)
    after_risk = risk.assess(augmented)
    safe_after = after_guidance.safe_daily_spending
    expected_ok = aff.min_after.get("expected", Decimal("0")) >= 0

    if plan.kind == "reduce_discretionary":
        feasible = plan.daily_saving_required <= funding.discretionary_daily_capacity(scenario)
    elif plan.kind == "use_savings":
        feasible = amount <= funding.available_now(scenario) and expected_ok
    else:
        feasible = expected_ok

    floor_preserved = plan.kind in ("use_savings", "wait_for_income", "split_into_stages")
    days_delay = (plan.purchase_date - scenario.today).days
    impact = _impact_level(base_safe_daily, safe_after, attrs.financial_importance, base_risk_level, after_risk.risk_level)
    score = _score(feasible, impact, days_delay, base_risk_level, after_risk.risk_level,
                   _soft_match(plan, request), floor_preserved)

    return DecisionStrategy(
        strategy_id=plan.kind,
        strategy_kind=plan.kind,
        purchase_date=plan.purchase_date,
        feasible=feasible,
        score=score,
        impact_level=impact,
        funding=plan.funding,
        savings_used=plan.savings_used,
        income_events_used=plan.income_events_used,
        expenses_to_reduce=plan.expenses_to_reduce,
        daily_saving_required=plan.daily_saving_required,
        saving_days=plan.saving_days,
        balance_after={"worst": str(aff.min_after.get("worst", Decimal("0"))),
                       "expected": str(aff.min_after.get("expected", Decimal("0")))},
        safe_daily_before=base_safe_daily,
        safe_daily_after=safe_after,
        risk_before=base_risk_level,
        risk_after=after_risk.risk_level,
        assumptions=plan.assumptions,
        tradeoffs=_tradeoffs(plan, days_delay=days_delay, safe_before=base_safe_daily, safe_after=safe_after,
                             floor_preserved=floor_preserved, expected_ok=expected_ok),
        constraints_used=plan.constraints_used,
    )


def evaluate(scenario: Scenario, request: DecisionRequest, *, behavior_view: dict | None = None) -> DecisionResult:
    attrs = classify(request, scenario)
    base_guidance = guidance.build(scenario)
    base_risk = risk.assess(scenario)
    base_safe_daily = base_guidance.safe_daily_spending

    plans: list[StrategyPlan] = []
    for generator in _GENERATORS:
        plan = (generator(request, attrs, scenario, behavior_view=behavior_view)
                if generator is strategies.plan_reduce_discretionary
                else generator(request, attrs, scenario))
        if plan is not None and plan.kind not in request.excluded_strategies:
            plans.append(plan)

    enriched = tuple(_enrich(p, request, attrs, scenario, base_safe_daily, base_risk.risk_level) for p in plans)

    buy_now = next((s for s in enriched if s.strategy_kind == "buy_now"), None)
    buy_now_worst = Decimal(buy_now.balance_after["worst"]) if buy_now else Decimal("-1")
    buy_now_expected = Decimal(buy_now.balance_after["expected"]) if buy_now else Decimal("-1")
    can_do_now = buy_now_expected >= 0
    feasible = [s for s in enriched if s.feasible]
    if buy_now_worst >= 0:
        verdict = "affordable"
    elif feasible:
        verdict = "tight"
    else:
        verdict = "not_now"

    best = max(feasible, key=lambda s: (s.score, -(s.purchase_date - scenario.today).days), default=None)

    # buy-now consequence + result-level impact summary
    intended = buy_now.purchase_date if buy_now else scenario.today
    now_consequence = {
        "balance_after_expected": buy_now.balance_after["expected"] if buy_now else None,
        "safe_daily_before": str(base_safe_daily),
        "safe_daily_after": str(buy_now.safe_daily_after) if buy_now else str(base_safe_daily),
        "risk_after": buy_now.risk_after if buy_now else base_risk.risk_level,
    }
    impact = ImpactSummary(
        daily_budget_after=buy_now.safe_daily_after if buy_now else base_safe_daily,
        weekly_budget_after=(buy_now.safe_daily_after if buy_now else base_safe_daily) * 7,
        monthly_remaining_after=guidance.build(_augment(scenario, request.amount_base, intended)[0]).threshold_remaining,
        savings_progress_after=None,
        days_until_recovery=_days_until_recovery(scenario, request.amount_base, intended),
        impact_level=buy_now.impact_level if buy_now else "significant",
    )

    deps = tuple(d.as_dict() for d in dependency.analyze_for(scenario, request.amount_base, intended))

    return DecisionResult(
        item_label=request.item_label,
        amount_base=request.amount_base,
        currency=scenario.base_currency,
        attributes=attrs,
        can_do_now=can_do_now,
        verdict=verdict,
        now_consequence=now_consequence,
        best_strategy=best,
        strategies=enriched,
        impact=impact,
        dependencies=deps,
    )
