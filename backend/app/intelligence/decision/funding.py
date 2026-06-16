"""Financial Decision Engine — funding math (C7a, pure).

Emergency-floor-aware savings allocation + income utilization + daily-save sizing.
Never drains the reserve: available_now keeps an emergency floor intact.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal

from app.intelligence.projection.scenario import Scenario

NEAR_TERM_DAYS = 30
DEFAULT_SAVE_DAYS = 14
DISCRETIONARY_CUT_FRACTION = Decimal("0.5")  # at most half of daily discretionary spend


def emergency_floor(scenario: Scenario) -> Decimal:
    """One month of spending (threshold if set, else mu*30) kept as a reserve."""
    mu_month = scenario.spending.mu * 30
    threshold = scenario.monthly_threshold or Decimal("0")
    return max(threshold, mu_month)


def committed_outflows(scenario: Scenario, *, within_days: int = NEAR_TERM_DAYS) -> Decimal:
    end = scenario.today + timedelta(days=within_days)
    return sum((o.amount_base for o in scenario.outflows if scenario.today <= o.date <= end), Decimal("0"))


def available_now(scenario: Scenario) -> Decimal:
    """Discretionary savings the user could spend today while keeping the floor
    and near-term commitments covered."""
    free = scenario.current_balance - emergency_floor(scenario) - committed_outflows(scenario)
    return max(Decimal("0"), free)


def counted_income_until(scenario: Scenario, when: date) -> Decimal:
    """Expected-mode income between today (exclusive) and `when` (inclusive):
    guaranteed at full value, sub-threshold risk-weighted."""
    tau = scenario.guaranteed_reliability_threshold
    total = Decimal("0")
    for e in scenario.income_events:
        if scenario.today < e.date <= when:
            total += e.amount_base if e.reliability >= tau else e.amount_base * e.reliability
    return total


def discretionary_daily_capacity(scenario: Scenario) -> Decimal:
    return scenario.spending.mu * DISCRETIONARY_CUT_FRACTION


def daily_save_required(gap: Decimal, days: int) -> Decimal:
    days = max(1, days)
    return (gap / days).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
