"""Pure tests for the dependency engine (derived, never stored)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection import dependency
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", income=(), outflows=()) -> Scenario:
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=120), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal("0"), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income), outflows=tuple(outflows),
    )


def _income(day, amount, rel="0.9", window=None):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal(rel), uuid.uuid4(), "receivable", window)


def _outflow(day, amount):
    return OutflowEvent(TODAY + timedelta(days=day), Decimal(amount), "event", uuid.uuid4(), False, 0)


def test_plan_depends_on_income():
    scn = _scn(balance="0", income=[_income(10, "10000")], outflows=[_outflow(12, "8000")])
    deps = dependency.analyze(scn)
    assert len(deps) == 1
    assert deps[0].income_amount == Decimal("10000")
    assert deps[0].risk == "low"  # reliability 0.9 >= tau


def test_no_dependency_when_balance_covers_it():
    scn = _scn(balance="100000", income=[_income(10, "10000")], outflows=[_outflow(12, "8000")])
    assert dependency.analyze(scn) == []


def test_dependency_risk_high_for_low_reliability():
    scn = _scn(balance="0", income=[_income(10, "10000", rel="0.5")], outflows=[_outflow(12, "8000")])
    deps = dependency.analyze(scn)
    assert deps and deps[0].risk == "high"


def test_dependency_carries_time_window():
    scn = _scn(balance="0", income=[_income(10, "10000", window="evening")], outflows=[_outflow(12, "8000")])
    deps = dependency.analyze(scn)
    assert deps and deps[0].income_time_window == "evening"


def test_analyze_for_hypothetical_decision():
    scn = _scn(balance="0", income=[_income(10, "10000")])
    deps = dependency.analyze_for(scn, Decimal("8000"), TODAY + timedelta(days=12))
    assert len(deps) == 1 and deps[0].dependent_kind == "decision"
