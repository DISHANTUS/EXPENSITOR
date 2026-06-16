"""Life-Easier context block — the numbers the user shouldn't have to compute.

Built from a Scenario + GuidanceResult (+ optional goal). Forward hooks
(income_time_window, savings_progress) stay None until those systems land.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.intelligence.projection.goal_feasibility import GoalFeasibilityResult
from app.intelligence.projection.guidance import GuidanceResult
from app.intelligence.projection.scenario import Scenario


@dataclass(frozen=True)
class LifeEasierContext:
    currency: str
    daily_remaining: Decimal
    weekly_remaining: Decimal
    monthly_discretionary_remaining: Decimal | None
    days_until_next_income: int | None
    next_income_date: date | None
    income_time_window: str | None = None          # rough arrival window, when known
    income_time_exact: str | None = None           # exact arrival time, when known
    next_income_amount: Decimal | None = None
    savings_progress: Decimal | None = None         # future/optional (needs a goal)
    amount_still_needed: Decimal | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "daily_remaining": str(self.daily_remaining),
            "weekly_remaining": str(self.weekly_remaining),
            "monthly_discretionary_remaining": (
                str(self.monthly_discretionary_remaining)
                if self.monthly_discretionary_remaining is not None else None
            ),
            "days_until_next_income": self.days_until_next_income,
            "next_income_date": self.next_income_date.isoformat() if self.next_income_date else None,
            "income_time_window": self.income_time_window,
            "income_time_exact": self.income_time_exact,
            "next_income_amount": str(self.next_income_amount) if self.next_income_amount is not None else None,
            "savings_progress": str(self.savings_progress) if self.savings_progress is not None else None,
            "amount_still_needed": str(self.amount_still_needed) if self.amount_still_needed is not None else None,
        }


def build_context(
    scenario: Scenario,
    guidance: GuidanceResult,
    *,
    goal_result: GoalFeasibilityResult | None = None,
) -> LifeEasierContext:
    # Next expected inflow (income_events are strictly future and sorted).
    next_event = scenario.income_events[0] if scenario.income_events else None
    days_until = (next_event.date - scenario.today).days if next_event else None

    savings_progress: Decimal | None = None
    amount_still_needed: Decimal | None = None
    if goal_result is not None and goal_result.goal_amount > 0:
        ratio = scenario.current_balance / goal_result.goal_amount
        savings_progress = max(Decimal("0"), min(Decimal("1"), ratio)).quantize(Decimal("0.001"))
        expected_surplus = goal_result.projected_surplus_or_shortfall.get("expected", Decimal("0"))
        amount_still_needed = -expected_surplus if expected_surplus < 0 else Decimal("0")

    return LifeEasierContext(
        currency=scenario.base_currency,
        daily_remaining=guidance.safe_daily_spending,
        weekly_remaining=guidance.safe_weekly_spending,
        monthly_discretionary_remaining=guidance.threshold_remaining,
        days_until_next_income=days_until,
        next_income_date=next_event.date if next_event else None,
        income_time_window=next_event.time_window if next_event else None,
        income_time_exact=(next_event.exact_time.strftime("%H:%M") if next_event and next_event.exact_time else None),
        next_income_amount=next_event.amount_base if next_event else None,
        savings_progress=savings_progress,
        amount_still_needed=amount_still_needed,
    )
