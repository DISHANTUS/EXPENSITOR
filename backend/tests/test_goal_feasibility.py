"""Pure tests for the Goal Feasibility Engine."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection.goal_feasibility import classify_confidence, evaluate
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", sigma="0", horizon_days=140, income=()):
    return Scenario(
        today=TODAY,
        horizon=TODAY + timedelta(days=horizon_days),
        base_currency="INR",
        current_balance=Decimal(balance),
        spending=SpendingModel(Decimal(mu), Decimal(sigma), "normal", 90, 90),
        income_events=tuple(income),
        outflows=(),
    )


def _income(day, amount, reliability):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal(reliability), uuid.uuid4())


def test_confidence_thresholds():
    assert classify_confidence(Decimal("0.80")) == "high"
    assert classify_confidence(Decimal("0.79")) == "medium"
    assert classify_confidence(Decimal("0.50")) == "medium"
    assert classify_confidence(Decimal("0.49")) == "low"


def test_feasible_goal():
    res = evaluate(_scn(balance="50000", mu="0"), Decimal("40000"), TODAY + timedelta(days=90))
    assert res.feasible is True
    assert res.projected_surplus_or_shortfall["expected"] == Decimal("10000")
    assert res.required_daily_saving == Decimal("0.00")
    assert res.probability >= Decimal("0.80") and res.confidence == "high"


def test_infeasible_goal_required_savings():
    res = evaluate(_scn(balance="0", mu="0"), Decimal("40000"), TODAY + timedelta(days=100))
    assert res.feasible is False
    assert res.projected_surplus_or_shortfall["expected"] == Decimal("-40000")
    assert res.required_daily_saving == Decimal("400.00")
    assert res.required_weekly_saving == Decimal("2800.00")
    assert res.required_monthly_saving == Decimal("12000.00")
    assert res.confidence == "low"


def test_scenario_ordering_worst_le_expected_le_best():
    s = _scn(balance="0", mu="0", income=[_income(10, "30000", "0.5")])
    res = evaluate(s, Decimal("10000"), TODAY + timedelta(days=20))
    surplus = res.projected_surplus_or_shortfall
    assert surplus["worst"] <= surplus["expected"] <= surplus["best"]
    assert res.feasible is True  # expected 15000 >= 10000


def test_probability_bounds():
    s = _scn(balance="20000", mu="50", sigma="200", income=[_income(10, "10000", "0.6")])
    res = evaluate(s, Decimal("25000"), TODAY + timedelta(days=30))
    assert Decimal("0") <= res.probability <= Decimal("1")


def test_target_in_past_is_guarded():
    res = evaluate(_scn(balance="100", mu="0"), Decimal("50"), TODAY - timedelta(days=5))
    assert res.feasible is True  # current balance 100 >= 50
    assert res.required_daily_saving == Decimal("0.00")  # no shortfall, days guarded
