"""Savings engine (pure, deterministic).

Goals are derived feasibility trackers — no money moves. Monthly targets project
the remainder of the month onto net-so-far; custom goals reuse goal_feasibility.
The base target is NEVER mutated: distribution is applied as a derived effective
target gated on the user's explicit recovery_mode.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.intelligence.projection import goal_feasibility
from app.intelligence.projection.calendar_utils import days_in_month
from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.scenario import Scenario
from app.intelligence.savings.state import CustomGoalState, MonthlyTargetState, SavingsReasons


def _counted_income(scenario: Scenario, start_exclusive: date, end_inclusive: date) -> Decimal:
    tau = scenario.guaranteed_reliability_threshold
    total = Decimal("0")
    for e in scenario.income_events:
        if start_exclusive < e.date <= end_inclusive:
            total += e.amount_base if e.reliability >= tau else e.amount_base * e.reliability
    return total


def evaluate_monthly_target(
    scenario: Scenario,
    *,
    base_target: Decimal,
    net_so_far: Decimal,
    carried_deficit: Decimal = Decimal("0"),
    recovery_mode: str | None = None,
    distribute_months: int | None = None,
) -> MonthlyTargetState:
    today = scenario.today
    dim = days_in_month(today.year, today.month)
    month_end = today.replace(day=dim)
    remaining_days = dim - today.day  # days strictly after today

    distributed = Decimal("0")
    if recovery_mode == "distribute" and distribute_months:
        distributed = carried_deficit / distribute_months
    effective_target = base_target + distributed

    remaining_income = _counted_income(scenario, today, month_end)
    remaining_planned = sum(
        (o.amount_base for o in scenario.outflows if today < o.date <= month_end), Decimal("0")
    )
    remaining_spend = scenario.spending.mu * remaining_days + remaining_planned
    projected_net = net_so_far + remaining_income - remaining_spend

    if net_so_far >= effective_target:
        status = "met"
    elif projected_net >= effective_target:
        status = "on_track"
    else:
        status = "behind"
    shortfall = max(Decimal("0"), effective_target - projected_net)
    progress = (net_so_far / effective_target) if effective_target > 0 else Decimal("0")

    return MonthlyTargetState(
        base_target=base_target, effective_target=effective_target, net_so_far=net_so_far,
        projected_net=projected_net, status=status, shortfall=shortfall,
        progress=max(Decimal("0"), progress).quantize(Decimal("0.001")),
    )


def evaluate_custom_goal(scenario: Scenario, *, target_amount: Decimal, target_date: date) -> CustomGoalState:
    gf = goal_feasibility.evaluate(scenario, target_amount, target_date)
    balance = scenario.current_balance
    progress = Decimal("0") if target_amount <= 0 else min(Decimal("1"), max(Decimal("0"), balance / target_amount))

    completion: date | None = None
    for point in project(scenario, ScenarioMode.expected):
        if point.balance >= target_amount:
            completion = point.date
            break

    if balance >= target_amount:
        status = "completed"
    elif gf.feasible:
        status = "on_track"
    else:
        status = "behind"
    expected_surplus = gf.projected_surplus_or_shortfall.get("expected", Decimal("0"))
    shortfall = -expected_surplus if expected_surplus < 0 else Decimal("0")

    return CustomGoalState(
        target_amount=target_amount, target_date=target_date,
        progress=progress.quantize(Decimal("0.001")), projected_completion_date=completion,
        feasible=gf.feasible, confidence=gf.confidence,
        required_daily_saving=gf.required_daily_saving, required_weekly_saving=gf.required_weekly_saving,
        required_monthly_saving=gf.required_monthly_saving, status=status, shortfall=shortfall,
    )


def savings_reasons(scenario: Scenario, *, window_end: date | None = None, behavior_view: dict | None = None) -> SavingsReasons:
    """Structured 'why at risk' contributors — facts only, nothing invented."""
    today = scenario.today
    if window_end is None:
        dim = days_in_month(today.year, today.month)
        window_end = today.replace(day=dim)
    decisions = tuple(
        {"date": o.date.isoformat(), "amount": str(o.amount_base), "priority": o.priority}
        for o in scenario.outflows if today <= o.date <= window_end
    )
    expenses = tuple((behavior_view or {}).get("overspending_categories", []))
    opportunities = tuple((behavior_view or {}).get("best_categories_to_cut", []))
    return SavingsReasons(expenses=expenses, decisions=decisions, opportunities=opportunities)
