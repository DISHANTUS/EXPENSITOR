"""Capability #15 — Goal Feasibility Engine (pure).

A goal is a *savings target* (NOT added as an outflow). Feasibility is based on
the EXPECTED scenario: feasible iff expected balance at the target date >= goal.
En-route insolvency is the Risk Engine's concern, not this one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.scenario import Scenario

_SD_FLOOR = 0.01
_Q = Decimal("0.01")


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def classify_confidence(probability: Decimal) -> str:
    if probability >= Decimal("0.80"):
        return "high"
    if probability >= Decimal("0.50"):
        return "medium"
    return "low"


@dataclass(frozen=True)
class GoalFeasibilityResult:
    goal_amount: Decimal
    target_date: date
    feasible: bool
    probability: Decimal
    confidence: str
    required_daily_saving: Decimal
    required_weekly_saving: Decimal
    required_monthly_saving: Decimal
    projected_surplus_or_shortfall: dict[str, Decimal]   # worst / expected / best


def _balance_on(points, when: date) -> Decimal:
    value = points[0].balance
    for point in points:
        if point.date <= when:
            value = point.balance
        else:
            break
    return value


def evaluate(scenario: Scenario, goal_amount: Decimal, target_date: date) -> GoalFeasibilityResult:
    effective = scenario.today if target_date < scenario.today else target_date
    curves = {mode: project(scenario, mode) for mode in ScenarioMode}
    balance_at = {mode.value: _balance_on(curves[mode], effective) for mode in ScenarioMode}
    surplus = {mode: balance_at[mode] - goal_amount for mode in balance_at}

    expected_balance = balance_at[ScenarioMode.expected.value]
    feasible = expected_balance >= goal_amount

    # Probability P(expected balance at target >= goal).
    days = max(0, (effective - scenario.today).days)
    variance = float(scenario.spending.sigma) ** 2 * days
    tau = scenario.guaranteed_reliability_threshold
    for event in scenario.income_events:
        if event.date <= effective and event.reliability < tau:
            p = float(event.reliability)
            a = float(event.amount_base)
            variance += a * a * p * (1.0 - p)
    sd = max(math.sqrt(variance) if variance > 0 else _SD_FLOOR, _SD_FLOOR)
    probability = _normal_cdf((float(expected_balance) - float(goal_amount)) / sd)
    probability = Decimal(str(round(min(1.0, max(0.0, probability)), 4)))
    confidence = classify_confidence(probability)

    # Required savings to close the EXPECTED shortfall by the target date.
    shortfall = goal_amount - expected_balance
    if shortfall < 0:
        shortfall = Decimal("0")
    days_until = max(1, (target_date - scenario.today).days)
    daily = shortfall / days_until

    return GoalFeasibilityResult(
        goal_amount=goal_amount,
        target_date=target_date,
        feasible=feasible,
        probability=probability,
        confidence=confidence,
        required_daily_saving=daily.quantize(_Q, rounding=ROUND_HALF_UP),
        required_weekly_saving=(daily * 7).quantize(_Q, rounding=ROUND_HALF_UP),
        required_monthly_saving=(daily * 30).quantize(_Q, rounding=ROUND_HALF_UP),
        projected_surplus_or_shortfall=surplus,
    )
