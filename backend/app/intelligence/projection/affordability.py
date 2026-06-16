"""Capability #12 — Affordability Engine (pure).

Verdict is decided SOLELY by the worst/expected band over the downstream window
[target_date, horizon]; probability is supplementary information only.

  GREEN  (affordable)   : worst   min_after >= 0
  AMBER  (conditional)  : worst   min_after <  0  AND  expected min_after >= 0
  RED    (unaffordable) : expected min_after <  0
"""

from __future__ import annotations

import dataclasses
import math
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario

_SD_FLOOR = 0.01


@dataclass(frozen=True)
class IncomeAssumption:
    source_id: uuid.UUID
    date: date
    amount_base: Decimal
    reliability: Decimal


@dataclass(frozen=True)
class AffordabilityResult:
    amount: Decimal
    target_date: date
    verdict: str                       # affordable | conditional | unaffordable
    affordable: bool                   # verdict == "affordable" (GREEN)
    balance_on_date: dict[str, Decimal]
    min_after: dict[str, Decimal]
    probability: Decimal               # supplementary, in [0, 1]
    assumptions: list[IncomeAssumption]
    shortfall: Decimal


def with_extra_outflow(scenario: Scenario, amount: Decimal, when: date) -> Scenario:
    """Return a copy of the scenario with a hypothetical outflow added (overdue
    targets clamped to today, matching real-outflow handling)."""
    overdue = when < scenario.today
    effective = scenario.today if overdue else when
    days_overdue = (scenario.today - when).days if overdue else 0
    extra = OutflowEvent(effective, amount, "hypothetical", uuid.uuid4(), overdue, days_overdue)
    horizon = max(scenario.horizon, effective)
    return dataclasses.replace(scenario, outflows=scenario.outflows + (extra,), horizon=horizon)


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _balance_on(points, when: date) -> Decimal:
    value = points[0].balance
    for point in points:
        if point.date <= when:
            value = point.balance
        else:
            break
    return value


def _min_after(points, when: date) -> Decimal:
    values = [p.balance for p in points if p.date >= when]
    return min(values) if values else points[-1].balance


def _probability(scenario: Scenario, effective: date, expected_points) -> Decimal:
    downstream = [p for p in expected_points if p.date >= effective]
    if not downstream:
        return Decimal("1")
    dip = min(downstream, key=lambda p: p.balance)
    days = max(0, (dip.date - scenario.today).days)
    variance = float(scenario.spending.sigma) ** 2 * days
    tau = scenario.guaranteed_reliability_threshold
    for event in scenario.income_events:
        if event.date <= dip.date and event.reliability < tau:
            p = float(event.reliability)
            a = float(event.amount_base)
            variance += a * a * p * (1.0 - p)
    sd = math.sqrt(variance) if variance > 0 else _SD_FLOOR
    sd = max(sd, _SD_FLOOR)
    probability = _normal_cdf(float(dip.balance) / sd)
    probability = min(1.0, max(0.0, probability))
    return Decimal(str(round(probability, 4)))


def _assumptions(scenario: Scenario) -> list[IncomeAssumption]:
    tau = scenario.guaranteed_reliability_threshold
    return [
        IncomeAssumption(e.source_id, e.date, e.amount_base, e.reliability)
        for e in scenario.income_events
        if e.reliability < tau and e.date <= scenario.horizon
    ]


def evaluate(scenario: Scenario, amount: Decimal, target_date: date) -> AffordabilityResult:
    effective = scenario.today if target_date < scenario.today else target_date
    augmented = with_extra_outflow(scenario, amount, target_date)
    curves = {mode: project(augmented, mode) for mode in ScenarioMode}

    balance_on_date = {mode.value: _balance_on(curves[mode], effective) for mode in ScenarioMode}
    min_after = {mode.value: _min_after(curves[mode], effective) for mode in ScenarioMode}

    worst = min_after[ScenarioMode.worst.value]
    expected = min_after[ScenarioMode.expected.value]
    if worst >= 0:
        verdict = "affordable"
    elif expected >= 0:
        verdict = "conditional"
    else:
        verdict = "unaffordable"

    shortfall = -expected if expected < 0 else Decimal("0")
    probability = _probability(augmented, effective, curves[ScenarioMode.expected])
    return AffordabilityResult(
        amount=amount,
        target_date=target_date,
        verdict=verdict,
        affordable=verdict == "affordable",
        balance_on_date=balance_on_date,
        min_after=min_after,
        probability=probability,
        assumptions=_assumptions(augmented),
        shortfall=shortfall,
    )
