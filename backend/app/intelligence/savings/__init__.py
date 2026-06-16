"""Savings engine (Tier 1) — deterministic savings targets + recovery planning.

Goals are derived feasibility trackers (no ledgers, no balance mutation). The
system proposes recovery options; the user decides. Reusable by the Advisor
layer, Decision Engine, and Companion via structured outputs.
"""

from __future__ import annotations

from app.intelligence.savings.engine import evaluate_custom_goal, evaluate_monthly_target, savings_reasons
from app.intelligence.savings.recovery import recovery_options
from app.intelligence.savings.state import (
    CustomGoalState,
    MonthlyTargetState,
    RecoveryOption,
    SavingsReasons,
)

__all__ = [
    "evaluate_custom_goal",
    "evaluate_monthly_target",
    "savings_reasons",
    "recovery_options",
    "CustomGoalState",
    "MonthlyTargetState",
    "RecoveryOption",
    "SavingsReasons",
]
