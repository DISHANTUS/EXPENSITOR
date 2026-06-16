"""Capabilities #2 / #9–11 — the projection walk (pure, deterministic).

Three modes (worst/expected/best) differ ONLY by income assumption; spending is
mu in all modes (sigma drives uncertainty later). To keep the invariant
worst(d) <= expected(d) <= best(d) valid, the EXPECTED mode counts guaranteed
income (reliability >= tau) at FULL value and risk-weights only sub-threshold
income (see IMPLEMENTATION NOTE in the summary).

Day-0 anchor: the start day uses current_balance minus today's/overdue outflows,
with NO predicted mu (today's actual spend is already in current_balance) and no
income (income is strictly > today). mu applies from today+1 onward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from app.intelligence.projection.scenario import Scenario


class ScenarioMode(str, Enum):
    worst = "worst"
    expected = "expected"
    best = "best"


@dataclass(frozen=True)
class DayBalance:
    date: date
    balance: Decimal


def _income_on(scenario: Scenario, day: date, mode: ScenarioMode) -> Decimal:
    tau = scenario.guaranteed_reliability_threshold
    total = Decimal(0)
    for event in scenario.income_events:
        if event.date != day:
            continue
        if mode == ScenarioMode.best:
            total += event.amount_base
        elif mode == ScenarioMode.worst:
            if event.reliability >= tau:
                total += event.amount_base
        else:  # expected
            if event.reliability >= tau:
                total += event.amount_base
            else:
                total += event.amount_base * event.reliability
    return total


def _outflow_on(scenario: Scenario, day: date) -> Decimal:
    return sum((event.amount_base for event in scenario.outflows if event.date == day), Decimal(0))


def project(scenario: Scenario, mode: ScenarioMode) -> list[DayBalance]:
    today = scenario.today
    mu = scenario.spending.mu

    # Day-0 anchor: today's & overdue outflows applied; no predicted mu; no income.
    balance = scenario.current_balance - _outflow_on(scenario, today)
    points = [DayBalance(today, balance)]

    day = today + timedelta(days=1)
    while day <= scenario.horizon:
        balance = balance + _income_on(scenario, day, mode) - mu - _outflow_on(scenario, day)
        points.append(DayBalance(day, balance))
        day += timedelta(days=1)
    return points


def project_all(scenario: Scenario) -> dict[ScenarioMode, list[DayBalance]]:
    return {mode: project(scenario, mode) for mode in ScenarioMode}


def min_balance(points: list[DayBalance]) -> DayBalance:
    return min(points, key=lambda point: point.balance)


def downsample(points: list[DayBalance], max_points: int = 120) -> list[DayBalance]:
    """Weekly boundary points for long horizons (keeps payloads bounded)."""
    if len(points) <= max_points:
        return points
    out = [points[index] for index in range(0, len(points), 7)]
    if out[-1].date != points[-1].date:
        out.append(points[-1])
    return out
