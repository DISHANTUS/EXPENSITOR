"""Pure tests for the reschedule engine (scoring factors per candidate)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection import reschedule
from app.intelligence.projection.budget_session_state import ActiveSession
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", horizon_days=60, income=(), outflows=(), sessions=()):
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=horizon_days), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal(mu), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income), outflows=tuple(outflows), active_sessions=tuple(sessions),
    )


def _income(day, amount, origin):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal("0.9"), uuid.uuid4(), origin)


def _outflow(planned_id, day, amount, *, priority="event"):
    return OutflowEvent(TODAY + timedelta(days=day), Decimal(amount), priority, planned_id, False, 0)


def test_moving_after_salary_scores_better():
    pid = uuid.uuid4()
    scn = _scn(balance="0", income=[_income(10, "25000", "income_source:salary")], outflows=[_outflow(pid, 5, "5000")])
    result = reschedule.analyze(scn, planned_id=pid, amount=Decimal("5000"), current_date=TODAY + timedelta(days=5), window_days=30)
    assert result.best_date is not None and result.best_date >= TODAY + timedelta(days=10)
    best = next(c for c in result.candidates if c.date == result.best_date)
    assert best.affordable
    assert any(f.type == "salary_arrival" and f.impact == Decimal("25000") for f in best.factors)


def test_receivable_arrival_factor():
    pid = uuid.uuid4()
    scn = _scn(balance="0", income=[_income(8, "5000", "receivable")], outflows=[_outflow(pid, 3, "4000")])
    result = reschedule.analyze(scn, planned_id=pid, amount=Decimal("4000"), current_date=TODAY + timedelta(days=3), window_days=20)
    after = next(c for c in result.candidates if c.date >= TODAY + timedelta(days=8))
    assert any(f.type == "receivable_arrival" and f.impact == Decimal("5000") for f in after.factors)


def test_planned_expense_before_event_factor():
    pid = uuid.uuid4()
    other = uuid.uuid4()
    scn = _scn(balance="10000", outflows=[_outflow(pid, 1, "1000"), _outflow(other, 3, "3000", priority="high")])
    result = reschedule.analyze(scn, planned_id=pid, amount=Decimal("1000"), current_date=TODAY + timedelta(days=1), window_days=10)
    candidate = next(c for c in result.candidates if c.date >= TODAY + timedelta(days=3))
    assert any(f.type == "planned_expense_before_event" and f.impact == Decimal("-3000") for f in candidate.factors)


def test_budget_session_overlap_factor():
    pid = uuid.uuid4()
    session = ActiveSession(uuid.uuid4(), "outing", Decimal("1000"), Decimal("0"), Decimal("0"))
    scn = _scn(balance="10000", outflows=[_outflow(pid, 2, "500")], sessions=[session])
    result = reschedule.analyze(scn, planned_id=pid, amount=Decimal("500"), current_date=TODAY + timedelta(days=2), window_days=5)
    assert all(any(f.type == "budget_session_overlap" and f.impact == -1 for f in c.factors) for c in result.candidates)


def test_window_capped():
    pid = uuid.uuid4()
    scn = _scn(balance="100000", horizon_days=400, outflows=[_outflow(pid, 0, "100")])
    result = reschedule.analyze(scn, planned_id=pid, amount=Decimal("100"), current_date=TODAY, window_days=200)
    assert result.window_days == reschedule.MAX_WINDOW_DAYS
    assert len(result.candidates) == reschedule.MAX_WINDOW_DAYS + 1  # inclusive of current_date


def test_score_in_range_and_ranking():
    pid = uuid.uuid4()
    scn = _scn(balance="100000", outflows=[_outflow(pid, 5, "1000")])
    result = reschedule.analyze(scn, planned_id=pid, amount=Decimal("1000"), current_date=TODAY + timedelta(days=5), window_days=10)
    assert all(0 <= c.score <= 100 for c in result.candidates)
    assert result.best_date is not None and result.worst_dates == []  # all affordable here
