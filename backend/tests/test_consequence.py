"""Pure tests for the consequence engine."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection import consequence
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", horizon_days=120, outflows=(), threshold=None):
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=horizon_days), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal(mu), Decimal("0"), "normal", 90, 90),
        income_events=(), outflows=tuple(outflows),
        monthly_threshold=Decimal(threshold) if threshold is not None else None,
    )


def _event(planned_id, day, amount):
    return OutflowEvent(TODAY + timedelta(days=day), Decimal(amount), "medium", planned_id, False, 0)


def test_affordable_event_no_adjustments():
    pid = uuid.uuid4()
    scn = _scn(balance="100000", outflows=[_event(pid, 10, "1000")])
    r = consequence.evaluate(scn, planned_id=pid, amount=Decimal("1000"), event_date=TODAY + timedelta(days=10))
    assert r.affordable is True
    assert r.required_adjustments == []
    assert r.affordability["verdict"] == "affordable"
    assert "without" in r.safe_daily_impact and "with" in r.safe_daily_impact


def test_unaffordable_event_has_structured_adjustments():
    pid = uuid.uuid4()
    scn = _scn(balance="0", outflows=[_event(pid, 10, "5000")])
    r = consequence.evaluate(scn, planned_id=pid, amount=Decimal("5000"), event_date=TODAY + timedelta(days=10))
    assert r.affordable is False
    assert r.affordability["shortfall"] == "5000"
    actions = {a.action for a in r.required_adjustments}
    assert "reduce_discretionary" in actions
    # adjustments are structured {action, data}
    assert all(isinstance(a.data, dict) for a in r.required_adjustments)


def test_threshold_impact_present_when_threshold_set():
    pid = uuid.uuid4()
    scn = _scn(balance="50000", outflows=[_event(pid, 10, "1000")], threshold="20000")
    r = consequence.evaluate(scn, planned_id=pid, amount=Decimal("1000"), event_date=TODAY + timedelta(days=10))
    assert r.threshold_impact is not None and "delta" in r.threshold_impact


def test_goal_feasibility_and_affordability_lenses():
    pid = uuid.uuid4()
    scn = _scn(balance="100000", outflows=[_event(pid, 20, "2000")])
    r = consequence.evaluate(scn, planned_id=pid, amount=Decimal("2000"), event_date=TODAY + timedelta(days=20))
    assert set(r.goal_feasibility) >= {"feasible", "probability", "required_daily_saving"}
    assert set(r.affordability) >= {"verdict", "probability", "shortfall"}


def test_balances_before_and_after():
    pid = uuid.uuid4()
    scn = _scn(balance="10000", outflows=[_event(pid, 10, "1000")])
    r = consequence.evaluate(scn, planned_id=pid, amount=Decimal("1000"), event_date=TODAY + timedelta(days=10))
    # before excludes the event, after includes it (-1000)
    assert r.projected_balance_on_date - r.projected_balance_after == Decimal("1000")
