"""Pure tests for the Life-Easier context block."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.advisor.context_block import build_context
from app.intelligence.projection.goal_feasibility import GoalFeasibilityResult
from app.intelligence.projection.guidance import GuidanceResult
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="50000", income=()) -> Scenario:
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=120), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal("0"), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income), outflows=(),
    )


def test_context_surfaces_remaining_and_next_income():
    income = (IncomeEvent(TODAY + timedelta(days=5), Decimal("20000"), Decimal("0.9"), uuid.uuid4(), "income_source:salary"),)
    guidance = GuidanceResult(Decimal("650"), Decimal("4550"), Decimal("2000"), [])
    ctx = build_context(_scn(income=income), guidance)
    assert ctx.daily_remaining == Decimal("650")
    assert ctx.weekly_remaining == Decimal("4550")
    assert ctx.monthly_discretionary_remaining == Decimal("2000")
    assert ctx.days_until_next_income == 5
    assert ctx.next_income_date == TODAY + timedelta(days=5)
    assert ctx.income_time_window is None  # future hook
    assert ctx.savings_progress is None    # no goal supplied


def test_context_with_goal_populates_savings_fields():
    guidance = GuidanceResult(Decimal("0"), Decimal("0"), None, [])
    goal = GoalFeasibilityResult(
        goal_amount=Decimal("100000"), target_date=TODAY + timedelta(days=30), feasible=False,
        probability=Decimal("0.5"), confidence="medium", required_daily_saving=Decimal("100"),
        required_weekly_saving=Decimal("700"), required_monthly_saving=Decimal("3000"),
        projected_surplus_or_shortfall={"worst": Decimal("-20000"), "expected": Decimal("-10000"), "best": Decimal("0")},
    )
    ctx = build_context(_scn(balance="50000"), guidance, goal_result=goal)
    assert ctx.savings_progress == Decimal("0.500")          # 50000 / 100000
    assert ctx.amount_still_needed == Decimal("10000")       # -expected shortfall
