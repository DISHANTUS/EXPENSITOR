"""Pure tests for the Risk Engine (synthetic Scenarios)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.risk import assess
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", horizon_days=30, income=(), outflows=(), threshold=None):
    return Scenario(
        today=TODAY,
        horizon=TODAY + timedelta(days=horizon_days),
        base_currency="INR",
        current_balance=Decimal(balance),
        spending=SpendingModel(Decimal(mu), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income),
        outflows=tuple(outflows),
        monthly_threshold=Decimal(threshold) if threshold is not None else None,
    )


def _income(day, amount, reliability):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal(reliability), uuid.uuid4())


def _outflow(day, amount, *, priority="medium", overdue=False, days_overdue=0):
    when = TODAY if overdue else TODAY + timedelta(days=day)
    return OutflowEvent(when, Decimal(amount), priority, uuid.uuid4(), overdue, days_overdue)


def _codes(assessment):
    return {s.code for s in assessment.signals}


def test_expected_negative_is_emergency_critical():
    a = assess(_scn(balance="0", mu="100", horizon_days=10))
    assert "expected_negative" in _codes(a)
    assert a.emergency_mode is True
    assert a.risk_level == "critical"
    assert a.risk_score >= 70


def test_worst_negative_not_emergency():
    # Sub-threshold income: worst dips (income dropped), expected stays >= 0.
    a = assess(_scn(balance="0", mu="0", income=[_income(5, "5000", "0.5")], outflows=[_outflow(10, "2000")]))
    assert "worst_negative" in _codes(a)
    assert "expected_negative" not in _codes(a)
    assert a.emergency_mode is False
    assert a.risk_level == "high"


def test_overdue_signal():
    a = assess(_scn(balance="100000", mu="0", outflows=[_outflow(0, "800", overdue=True, days_overdue=9)]))
    assert "overdue_planned_expense" in _codes(a)
    signal = next(s for s in a.signals if s.code == "overdue_planned_expense")
    assert signal.data["count"] == 1 and signal.data["max_days_overdue"] == 9


def test_low_buffer_signal():
    # Min expected balance positive but below 3*mu (=300).
    a = assess(_scn(balance="1000", mu="100", horizon_days=8))
    assert "low_buffer" in _codes(a)
    assert a.emergency_mode is False
    assert a.risk_level == "moderate"


def test_threshold_pace_moderate():
    # June has 30 days; mu*30 = 3150 vs threshold 3000 -> 5% over -> moderate.
    a = assess(_scn(balance="1000000", mu="105", horizon_days=30, threshold="3000"))
    signal = next(s for s in a.signals if s.code == "threshold_pace")
    assert signal.severity == "moderate"


def test_threshold_pace_high():
    # mu*30 = 3600 vs 3000 -> 20% over -> high.
    a = assess(_scn(balance="1000000", mu="120", horizon_days=30, threshold="3000"))
    signal = next(s for s in a.signals if s.code == "threshold_pace")
    assert signal.severity == "high"
    assert a.risk_level == "high"


def test_risk_score_bounds_and_none_level():
    healthy = assess(_scn(balance="100000", mu="0", horizon_days=30))
    assert healthy.risk_level == "none"
    assert healthy.risk_score == 0
    assert healthy.signals == []
    severe = assess(_scn(balance="0", mu="500", horizon_days=30))
    assert 0 <= severe.risk_score <= 100


def test_recovery_plan_generation():
    a = assess(
        _scn(
            balance="100",
            mu="200",
            horizon_days=10,
            outflows=[_outflow(3, "500", priority="medium"), _outflow(4, "800", priority="critical")],
        )
    )
    assert a.emergency_mode is True
    actions = {act.action for act in a.recovery_plan}
    assert "defer_planned" in actions and "reduce_discretionary" in actions
    defer = next(act for act in a.recovery_plan if act.action == "defer_planned")
    # only the low/medium candidate is offered, not the critical one
    assert len(defer.data["candidates"]) == 1
    assert defer.data["candidates"][0]["priority"] == "medium"
