"""Pure tests for the Guidance Engine."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection import risk
from app.intelligence.projection.guidance import build
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

MID_MONTH = date(2026, 6, 10)  # day 10 of a 30-day month -> 21 days remaining


def _scn(*, today=MID_MONTH, balance="0", mu="0", horizon_days=30, income=(), outflows=(), threshold=None):
    return Scenario(
        today=today,
        horizon=today + timedelta(days=horizon_days),
        base_currency="INR",
        current_balance=Decimal(balance),
        spending=SpendingModel(Decimal(mu), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income),
        outflows=tuple(outflows),
        monthly_threshold=Decimal(threshold) if threshold is not None else None,
    )


def _outflow(d, amount, *, priority="medium"):
    return OutflowEvent(d, Decimal(amount), priority, uuid.uuid4(), False, 0)


def test_income_based_safe_daily():
    s = _scn(balance="21000", mu="0")  # 21000 / 21 days = 1000/day
    g = build(s, risk.assess(s))
    assert g.safe_daily_spending == Decimal("1000.00")
    assert g.safe_weekly_spending == Decimal("7000.00")
    assert g.threshold_remaining is None
    assert any(a.action == "daily_spend_limit" for a in g.recommended_actions)


def test_threshold_binding():
    s = _scn(balance="100000", mu="100", threshold="5000")  # spent_mtd = 100*10 = 1000
    g = build(s, risk.assess(s))
    assert g.threshold_remaining == Decimal("4000.00")       # 5000 - 1000
    assert g.safe_daily_spending == Decimal("190.48")        # 4000 / 21, tighter than income-based
    assert any(a.action == "threshold_binding" for a in g.recommended_actions)


def test_last_day_of_month_no_division_error():
    s = _scn(today=date(2026, 6, 30), balance="500", mu="0")  # days_remaining = 1
    g = build(s, risk.assess(s))
    assert g.safe_daily_spending == Decimal("500.00")


def test_actions_are_structured_no_prose():
    s = _scn(balance="21000", mu="0", threshold="100000")
    g = build(s, risk.assess(s))
    for action in g.recommended_actions:
        assert isinstance(action.action, str) and " " not in action.action
        assert isinstance(action.data, dict)


def test_risk_recovery_passthrough_on_emergency():
    s = _scn(balance="100", mu="200", horizon_days=10, outflows=[_outflow(MID_MONTH + timedelta(days=3), "500")])
    assessment = risk.assess(s)
    assert assessment.emergency_mode is True
    g = build(s, assessment)
    codes = {a.action for a in g.recommended_actions}
    assert "reduce_discretionary" in codes and "defer_planned" in codes
