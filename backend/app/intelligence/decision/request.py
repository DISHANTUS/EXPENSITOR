"""Financial Decision Engine — request + attribute enums (C7a).

Generalized: the engine reasons over ABSTRACT attributes, never over named
scenarios (phone/outing/subscription/...). The same request shape covers any
financial decision.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class DecisionKind(str, enum.Enum):
    purchase = "purchase"
    subscription = "subscription"
    emi = "emi"
    outing = "outing"
    travel = "travel"
    investment = "investment"
    loan_given = "loan_given"
    donation = "donation"
    savings_goal = "savings_goal"
    custom = "custom"


class OutflowShape(str, enum.Enum):
    one_time = "one_time"
    recurring = "recurring"
    tenured = "tenured"


class Flexibility(str, enum.Enum):
    fixed_date = "fixed_date"   # must happen on a specific date
    flexible = "flexible"       # date can shift within reason
    deferrable = "deferrable"   # can be delayed indefinitely


class EmotionalImportance(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class StrategyKind(str, enum.Enum):
    buy_now = "buy_now"
    use_savings = "use_savings"
    wait_for_income = "wait_for_income"
    reduce_discretionary = "reduce_discretionary"
    split_into_stages = "split_into_stages"
    move_date = "move_date"


@dataclass(frozen=True)
class UserConstraints:
    """The user is the final decision maker. Hard constraints BLOCK strategies;
    soft preferences PRIORITIZE them. The engine never suggests a blocked path."""

    # --- hard constraints ---
    date_fixed: bool = False        # the date cannot move (event, flight, family commitment)
    no_savings: bool = False        # savings must not be used
    no_delay: bool = False          # cannot be delayed (must do now)
    mandatory: bool = False         # cannot be skipped (subscription for work, EMI)
    # --- soft preferences ---
    willing_to_delay: bool = False
    willing_to_use_savings: bool = False
    willing_to_reduce_spending: bool = False
    reducible_categories: tuple[str, ...] = ()   # categories the user is happy to trim


@dataclass(frozen=True)
class DecisionRequest:
    item_label: str
    amount_base: Decimal
    decision_kind: DecisionKind = DecisionKind.purchase
    outflow_shape: OutflowShape = OutflowShape.one_time
    recurrence_months: int | None = None     # recurring cadence (months)
    tenure_months: int | None = None         # tenured (EMI) length
    target_date: date | None = None
    flexibility: Flexibility = Flexibility.flexible
    emotional_importance: EmotionalImportance = EmotionalImportance.medium
    constraints: UserConstraints = field(default_factory=UserConstraints)
    # Recommendation-memory hook (no persistence yet): strategy kinds to skip.
    excluded_strategies: tuple[str, ...] = ()
