"""Pure-function tests for the projection engine (synthetic Scenarios, no DB)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection.engine import (
    DayBalance,
    ScenarioMode,
    min_balance,
    project,
    project_all,
)
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _spending(mu: str = "0", sigma: str = "0") -> SpendingModel:
    return SpendingModel(mu=Decimal(mu), sigma=Decimal(sigma), confidence="normal", observed_days=90, window_days=90)


def _scenario(*, horizon_days: int, balance: str = "1000", mu: str = "0", income=(), outflows=()) -> Scenario:
    return Scenario(
        today=TODAY,
        horizon=TODAY + timedelta(days=horizon_days),
        base_currency="INR",
        current_balance=Decimal(balance),
        spending=_spending(mu),
        income_events=tuple(income),
        outflows=tuple(outflows),
    )


def _income(day_offset: int, amount: str, reliability: str) -> IncomeEvent:
    return IncomeEvent(TODAY + timedelta(days=day_offset), Decimal(amount), Decimal(reliability), uuid.uuid4())


def _outflow(day_offset: int, amount: str, overdue: bool = False, days_overdue: int = 0) -> OutflowEvent:
    return OutflowEvent(TODAY + timedelta(days=day_offset), Decimal(amount), "medium", uuid.uuid4(), overdue, days_overdue)


def test_flat_when_no_activity():
    s = _scenario(horizon_days=3, balance="1000", mu="0")
    pts = project(s, ScenarioMode.expected)
    assert [p.balance for p in pts] == [Decimal("1000")] * 4


def test_mu_reduces_each_future_day_not_today():
    s = _scenario(horizon_days=3, balance="100", mu="10")
    pts = project(s, ScenarioMode.expected)
    # Day 0 (today) keeps balance (today's spend already in current_balance).
    assert [p.balance for p in pts] == [Decimal("100"), Decimal("90"), Decimal("80"), Decimal("70")]


def test_income_applies_only_after_today():
    s = _scenario(horizon_days=3, balance="100", mu="0", income=[_income(0, "50", "1.0"), _income(2, "50", "1.0")])
    pts = project(s, ScenarioMode.expected)
    # day-0 income event is ignored (income strictly > today); day+2 adds 50.
    assert [p.balance for p in pts] == [Decimal("100"), Decimal("100"), Decimal("150"), Decimal("150")]


def test_overdue_outflow_clamped_to_day_zero():
    s = _scenario(horizon_days=2, balance="100", mu="0", outflows=[_outflow(0, "30", overdue=True, days_overdue=5)])
    pts = project(s, ScenarioMode.expected)
    assert pts[0].balance == Decimal("70")  # applied at anchor
    assert pts[1].balance == Decimal("70")


def test_guaranteed_income_full_in_all_modes():
    s = _scenario(horizon_days=1, balance="0", mu="0", income=[_income(1, "100", "0.9")])
    assert project(s, ScenarioMode.worst)[-1].balance == Decimal("100")
    assert project(s, ScenarioMode.expected)[-1].balance == Decimal("100.0")
    assert project(s, ScenarioMode.best)[-1].balance == Decimal("100")


def test_subthreshold_income_weighting():
    s = _scenario(horizon_days=1, balance="0", mu="0", income=[_income(1, "100", "0.5")])
    assert project(s, ScenarioMode.worst)[-1].balance == Decimal("0")      # dropped
    assert project(s, ScenarioMode.expected)[-1].balance == Decimal("50.0")  # 100 * 0.5
    assert project(s, ScenarioMode.best)[-1].balance == Decimal("100")


def test_worst_le_expected_le_best_invariant():
    s = _scenario(
        horizon_days=30,
        balance="1000",
        mu="20",
        income=[_income(10, "5000", "0.9"), _income(20, "3000", "0.5")],
        outflows=[_outflow(15, "1000")],
    )
    curves = project_all(s)
    for w, e, b in zip(curves[ScenarioMode.worst], curves[ScenarioMode.expected], curves[ScenarioMode.best], strict=True):
        assert w.balance <= e.balance <= b.balance


def test_horizon_inclusive_point_count():
    s = _scenario(horizon_days=10, balance="0", mu="0")
    assert len(project(s, ScenarioMode.expected)) == 11  # today .. today+10 inclusive


def test_single_day_horizon():
    s = _scenario(horizon_days=0, balance="500", mu="99")
    pts = project(s, ScenarioMode.expected)
    assert len(pts) == 1 and pts[0].balance == Decimal("500")


def test_min_balance_helper():
    s = _scenario(horizon_days=3, balance="100", mu="40")
    assert min_balance(project(s, ScenarioMode.expected)).balance == Decimal("-20")
