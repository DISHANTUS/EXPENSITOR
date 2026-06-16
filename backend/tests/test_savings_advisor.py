"""Pure tests for savings + dependency advisor explainers (tone-guarded)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.advisor import explainers, tone
from app.intelligence.projection import dependency
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel
from app.intelligence.savings import engine, recovery
from app.intelligence.savings.state import SavingsReasons

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", income=(), outflows=()):
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=120), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal("0"), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income), outflows=tuple(outflows),
    )


def _clean(exp):
    for t in exp.texts():
        assert tone.lint(t) == [], f"judgmental text: {t!r}"
    assert exp.render()


def test_explain_monthly_target_behind_offers_recovery():
    state = engine.evaluate_monthly_target(_scn(), base_target=Decimal("50000"), net_so_far=Decimal("45000"))
    options = recovery.recovery_options(state.shortfall)
    exp = explainers.explain_monthly_target(state, SavingsReasons(), options, currency="INR")
    assert exp.severity == "warning"
    assert {a.action for a in exp.alternative_actions} == {"keep_unchanged", "distribute", "new_plan"}
    _clean(exp)


def test_explain_custom_goal_behind():
    state = engine.evaluate_custom_goal(_scn(balance="10000"), target_amount=Decimal("100000"),
                                        target_date=TODAY + timedelta(days=60))
    exp = explainers.explain_custom_goal(state, SavingsReasons(), currency="INR")
    assert exp.best_next_action.action == "save_daily"
    _clean(exp)


def test_explain_dependency_mentions_amount_window_and_options():
    income = IncomeEvent(TODAY + timedelta(days=10), Decimal("5000"), Decimal("0.6"), uuid.uuid4(), "receivable", "evening")
    outflow = OutflowEvent(TODAY + timedelta(days=12), Decimal("4000"), "event", uuid.uuid4(), False, 0)
    deps = dependency.analyze(_scn(balance="0", income=[income], outflows=[outflow]))
    assert deps
    exp = explainers.explain_dependency(deps[0], currency="INR", item_label="Your outing")
    assert "5,000" in exp.headline and "evening" in exp.headline
    assert "use savings" in exp.impact
    _clean(exp)
