"""Derived budget summary (Budget Setup output)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class BudgetSummary(BaseModel):
    base_currency: str
    monthly_income: Decimal
    monthly_commitments: Decimal       # recurring_rules (subscriptions/EMI/bills/...)
    monthly_goal_contributions: Decimal  # active monthly_target savings goals
    monthly_discretionary: Decimal     # income − commitments − goals (floored at 0)
    weekly_budget: Decimal
    daily_budget: Decimal
