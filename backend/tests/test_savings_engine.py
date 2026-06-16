"""Pure tests for the savings engine + recovery (Tier 1)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel
from app.intelligence.savings import engine, recovery

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", income=(), outflows=(), horizon_days=200) -> Scenario:
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=horizon_days), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal(mu), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income), outflows=tuple(outflows),
    )


def _income(day, amount, rel="0.9"):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal(rel), uuid.uuid4(), "income_source:salary")


def test_monthly_target_behind():
    state = engine.evaluate_monthly_target(_scn(), base_target=Decimal("50000"), net_so_far=Decimal("45000"))
    assert state.status == "behind"
    assert state.shortfall == Decimal("5000")
    assert state.progress == Decimal("0.900")


def test_monthly_target_on_track_with_income():
    scn = _scn(income=[_income(10, "40000")])
    state = engine.evaluate_monthly_target(scn, base_target=Decimal("50000"), net_so_far=Decimal("20000"))
    assert state.status == "on_track"
    assert state.projected_net == Decimal("60000")


def test_distribute_does_not_mutate_base_target():
    state = engine.evaluate_monthly_target(
        _scn(), base_target=Decimal("50000"), net_so_far=Decimal("0"),
        carried_deficit=Decimal("6000"), recovery_mode="distribute", distribute_months=3,
    )
    assert state.base_target == Decimal("50000")        # base untouched
    assert state.effective_target == Decimal("52000")   # +6000/3 derived


def test_custom_goal_behind_and_progress():
    scn = _scn(balance="50000")
    state = engine.evaluate_custom_goal(scn, target_amount=Decimal("100000"), target_date=TODAY + timedelta(days=60))
    assert state.status == "behind"
    assert state.progress == Decimal("0.500")
    assert state.projected_completion_date is None  # never reaches target with no income
    assert state.shortfall == Decimal("50000")


def test_custom_goal_completed_when_balance_exceeds():
    scn = _scn(balance="50000")
    state = engine.evaluate_custom_goal(scn, target_amount=Decimal("40000"), target_date=TODAY + timedelta(days=30))
    assert state.status == "completed" and state.progress == Decimal("1.000")


def test_custom_goal_on_track_with_income():
    scn = _scn(balance="30000", income=[_income(10, "50000")])
    state = engine.evaluate_custom_goal(scn, target_amount=Decimal("60000"), target_date=TODAY + timedelta(days=40))
    assert state.status == "on_track"
    assert state.projected_completion_date is not None


def test_recovery_options_structured_and_excludable():
    opts = recovery.recovery_options(Decimal("6000"), distribute_months=3)
    choices = {o.choice for o in opts}
    assert choices == {"keep_unchanged", "distribute", "new_plan"}
    distribute = next(o for o in opts if o.choice == "distribute")
    assert distribute.data["per_month_add"] == "2000.00"
    # rejecting a choice removes it (so it isn't suggested again)
    remaining = recovery.recovery_options(Decimal("6000"), excluded=("distribute",))
    assert "distribute" not in {o.choice for o in remaining}


def test_savings_reasons_from_facts():
    pid = uuid.uuid4()
    outflow = OutflowEvent(TODAY + timedelta(days=5), Decimal("3000"), "high", pid, False, 0)
    reasons = engine.savings_reasons(
        _scn(outflows=[outflow]),
        behavior_view={"overspending_categories": [{"category": "Shopping", "share": 0.3}],
                       "best_categories_to_cut": [{"category": "Food & Dining"}]},
    )
    assert reasons.decisions and reasons.decisions[0]["amount"] == "3000"
    assert reasons.expenses[0]["category"] == "Shopping"
    assert reasons.opportunities[0]["category"] == "Food & Dining"
