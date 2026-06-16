"""Financial Decision Engine — attribute classifier (C7a).

Maps a request + scenario into an abstract attribute vector. Rule-based and
deterministic — NO LLM, NO per-scenario special-casing. The whole engine then
reasons over these attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.intelligence.decision.request import DecisionKind, DecisionRequest, Flexibility
from app.intelligence.projection.scenario import Scenario

# decision_kind -> liquidity_class
_LIQUIDITY = {
    DecisionKind.purchase: "durable_asset",
    DecisionKind.subscription: "consumable",
    DecisionKind.emi: "durable_asset",
    DecisionKind.outing: "consumable",
    DecisionKind.travel: "consumable",
    DecisionKind.investment: "investment",
    DecisionKind.loan_given: "transfer",
    DecisionKind.donation: "transfer",
    DecisionKind.savings_goal: "investment",
    DecisionKind.custom: "consumable",
}

# financial_importance thresholds (amount as a share of current balance)
_MINOR_SHARE = Decimal("0.05")
_MODERATE_SHARE = Decimal("0.25")


@dataclass(frozen=True)
class DecisionAttributes:
    outflow_shape: str
    liquidity_class: str
    flexibility: str
    timing_constraint: str       # none | deadline
    essentiality: str            # essential | discretionary
    emotional_importance: str
    financial_importance: str    # minor | moderate | significant
    reversibility: str           # reversible | hard_to_reverse
    mandatory: bool
    can_move_date: bool
    can_use_savings: bool
    can_delay: bool
    can_reduce_spending: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "outflow_shape": self.outflow_shape,
            "liquidity_class": self.liquidity_class,
            "flexibility": self.flexibility,
            "timing_constraint": self.timing_constraint,
            "essentiality": self.essentiality,
            "emotional_importance": self.emotional_importance,
            "financial_importance": self.financial_importance,
            "reversibility": self.reversibility,
            "mandatory": self.mandatory,
            "can_move_date": self.can_move_date,
            "can_use_savings": self.can_use_savings,
            "can_delay": self.can_delay,
            "can_reduce_spending": self.can_reduce_spending,
        }


def _financial_importance(amount: Decimal, balance: Decimal) -> str:
    if balance <= 0:
        return "significant"
    share = amount / balance
    if share < _MINOR_SHARE:
        return "minor"
    if share < _MODERATE_SHARE:
        return "moderate"
    return "significant"


def classify(request: DecisionRequest, scenario: Scenario) -> DecisionAttributes:
    c = request.constraints
    liquidity = _LIQUIDITY.get(request.decision_kind, "consumable")
    essentiality = "essential" if c.mandatory else "discretionary"
    reversibility = "reversible" if liquidity in ("consumable", "transfer") else "hard_to_reverse"
    timing = "deadline" if (request.target_date is not None and request.flexibility == Flexibility.fixed_date) else "none"

    date_fixed = c.date_fixed or request.flexibility == Flexibility.fixed_date
    return DecisionAttributes(
        outflow_shape=request.outflow_shape.value,
        liquidity_class=liquidity,
        flexibility=request.flexibility.value,
        timing_constraint=timing,
        essentiality=essentiality,
        emotional_importance=request.emotional_importance.value,
        financial_importance=_financial_importance(request.amount_base, scenario.current_balance),
        reversibility=reversibility,
        mandatory=c.mandatory,
        can_move_date=not date_fixed,
        can_use_savings=not c.no_savings,
        can_delay=not (c.no_delay or date_fixed),
        can_reduce_spending=True,   # always an option; soft prefs set priority
    )
