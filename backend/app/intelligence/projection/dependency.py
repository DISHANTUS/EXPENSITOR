"""Dependency analysis (pure, derived — never stored).

A plan/decision "depends on" an expected inflow when removing that inflow would
push the projected balance below zero on or before the plan's date. Found by
counterfactual: drop each income event and re-check the expected min-balance.
Used by the Advisor layer, Decision Engine, Event Planner, etc.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario


@dataclass(frozen=True)
class Dependency:
    dependent_kind: str            # planned_expense | decision
    dependent_id: str | None
    dependent_date: date
    dependent_amount: Decimal
    income_source_id: str
    income_origin: str
    income_date: date
    income_amount: Decimal
    income_reliability: Decimal
    income_time_window: str | None
    risk: str                      # low | moderate | high

    def as_dict(self) -> dict[str, Any]:
        return {
            "dependent_kind": self.dependent_kind,
            "dependent_id": self.dependent_id,
            "dependent_date": self.dependent_date.isoformat(),
            "dependent_amount": str(self.dependent_amount),
            "income_source_id": self.income_source_id,
            "income_origin": self.income_origin,
            "income_date": self.income_date.isoformat(),
            "income_amount": str(self.income_amount),
            "income_reliability": str(self.income_reliability),
            "income_time_window": self.income_time_window,
            "risk": self.risk,
        }


def _risk(reliability: Decimal, tau: Decimal) -> str:
    if reliability >= tau:
        return "low"
    if reliability >= Decimal("0.6"):
        return "moderate"
    return "high"


def _min_until(scenario: Scenario, until: date) -> Decimal:
    # Best mode (income at face value): tests whether the plan is covered IF the
    # money arrives. Reliability then drives the dependency RISK, not its existence.
    points = project(scenario, ScenarioMode.best)
    values = [p.balance for p in points if p.date <= until]
    return min(values) if values else points[0].balance


def _deps_for(scenario: Scenario, *, dependent_kind: str, dependent_id: str | None,
              when: date, amount: Decimal) -> list[Dependency]:
    # If the plan is underfunded even WITH all income, it's a risk, not a single dependency.
    if _min_until(scenario, when) < 0:
        return []
    tau = scenario.guaranteed_reliability_threshold
    deps: list[Dependency] = []
    for i, e in enumerate(scenario.income_events):
        if not (scenario.today < e.date <= when):
            continue
        without = dataclasses.replace(
            scenario, income_events=tuple(x for j, x in enumerate(scenario.income_events) if j != i)
        )
        if _min_until(without, when) < 0:
            deps.append(Dependency(
                dependent_kind=dependent_kind, dependent_id=dependent_id, dependent_date=when,
                dependent_amount=amount, income_source_id=str(e.source_id), income_origin=e.origin,
                income_date=e.date, income_amount=e.amount_base, income_reliability=e.reliability,
                income_time_window=e.time_window, risk=_risk(e.reliability, tau),
            ))
    return deps


def analyze(scenario: Scenario) -> list[Dependency]:
    """Dependencies for every future planned outflow."""
    out: list[Dependency] = []
    for o in scenario.outflows:
        if o.overdue or o.date <= scenario.today:
            continue
        out.extend(_deps_for(scenario, dependent_kind="planned_expense", dependent_id=str(o.planned_id),
                             when=o.date, amount=o.amount_base))
    return out


def analyze_for(scenario: Scenario, amount: Decimal, when: date) -> list[Dependency]:
    """Dependencies for a hypothetical decision outflow at ``when``."""
    effective = max(scenario.today, when)
    extra = OutflowEvent(effective, amount, "hypothetical", uuid.uuid4(), when < scenario.today,
                         (scenario.today - when).days if when < scenario.today else 0)
    horizon = max(scenario.horizon, effective)
    augmented = dataclasses.replace(scenario, outflows=scenario.outflows + (extra,), horizon=horizon)
    return _deps_for(augmented, dependent_kind="decision", dependent_id=None, when=effective, amount=amount)
