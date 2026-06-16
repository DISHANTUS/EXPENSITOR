"""Decision Modifier framework (C7a-2) — generic, attribute/flag-gated analyzers.

One registry; each analyzer declares trigger() + required_inputs() + run(). The
system asks ONLY the minimum (Information Utility Rule), never assumes, and emits
structured findings (finding/impact/reasoning/recommendation/alternatives +
recovery_time_days). No product-specific logic — gating is by flags/attributes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.intelligence.projection.engine import ScenarioMode, project
from app.intelligence.projection.scenario import Scenario


# --- user-input model (all optional; collected via the influence step + follow-ups) ---
@dataclass(frozen=True)
class ModifierInputs:
    involves: tuple[str, ...] | None = None     # None => ask the influence step first
    original_amount: Decimal | None = None      # shared by free_delivery / offer / decision_change
    final_amount: Decimal | None = None
    items_useful: str | None = None             # would_have_bought_anyway: yes | maybe | no
    delivery_fee: Decimal | None = None
    free_delivery_threshold: Decimal | None = None
    offer: dict[str, Any] | None = None         # {kind, threshold?, discount?, cashback?, percent?, points_value?}
    bundle_add_ons: tuple[dict[str, Any], ...] | None = None  # [{name, cost, required}]
    hidden_items: tuple[dict[str, Any], ...] | None = None    # [{name, cost, recurring}]
    subscription: dict[str, Any] | None = None  # {alt_cadence, alt_price, expected_usage_months}
    emi: dict[str, Any] | None = None           # {down_payment, installment, duration_months, cash_price?}
    cancel_cost: Decimal | None = None
    change_trigger: str | None = None           # offer|cashback|free_delivery|bundle|urgency|social_pressure|emotional


@dataclass(frozen=True)
class GoalRef:
    kind: str                  # monthly_target | custom_goal
    name: str
    target_amount: Decimal
    target_date: date | None


@dataclass(frozen=True)
class AnalyzerCtx:
    request: Any               # DecisionRequest
    attributes: Any            # DecisionAttributes
    scenario: Scenario
    inputs: ModifierInputs
    currency: str
    amount: Decimal            # decision amount (base)
    when: date                 # intended date
    behavior_view: dict | None = None
    decision_result: Any = None
    goals: tuple[GoalRef, ...] = ()
    net_so_far: Decimal = Decimal("0")


@dataclass(frozen=True)
class Question:
    analyzer: str
    key: str
    prompt: str
    type: str                  # amount | choice | bool | money_list
    options: tuple[str, ...] = ()
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"analyzer": self.analyzer, "key": self.key, "prompt": self.prompt,
                "type": self.type, "options": list(self.options), "why": self.why}


@dataclass(frozen=True)
class ModifierFinding:
    analyzer: str
    finding: str
    impact: str
    reasoning: str
    recommendation: str
    alternatives: tuple[str, ...] = ()
    recovery_time_days: int | None = None
    facts: dict[str, Any] = field(default_factory=dict)

    def texts(self) -> list[str]:
        return [self.finding, self.impact, self.reasoning, self.recommendation, *self.alternatives]

    def as_dict(self) -> dict[str, Any]:
        return {
            "analyzer": self.analyzer, "finding": self.finding, "impact": self.impact,
            "reasoning": self.reasoning, "recommendation": self.recommendation,
            "alternatives": list(self.alternatives), "recovery_time_days": self.recovery_time_days,
            "facts": self.facts,
        }


@dataclass(frozen=True)
class ModifierAnalyzer:
    key: str
    trigger: Callable[[AnalyzerCtx], bool]
    required_inputs: Callable[[AnalyzerCtx], list[Question]]
    run: Callable[[AnalyzerCtx], ModifierFinding | None]


MODIFIER_REGISTRY: dict[str, ModifierAnalyzer] = {}


def register(key: str, *, trigger, required_inputs=None, run) -> None:
    if key in MODIFIER_REGISTRY:
        raise ValueError(f"Duplicate modifier analyzer: {key}")
    MODIFIER_REGISTRY[key] = ModifierAnalyzer(
        key=key, trigger=trigger,
        required_inputs=required_inputs or (lambda ctx: []), run=run,
    )


# The single influence-selection step (asked first, when involves is unknown).
INFLUENCE_OPTIONS = (
    "offer", "cashback", "free_delivery", "bundle", "emi", "subscription_pricing",
    "urgency", "social_pressure", "emotional", "none",
)
INFLUENCE_QUESTION = Question(
    analyzer="influence", key="involves", prompt="Did anything influence this purchase?",
    type="choice", options=INFLUENCE_OPTIONS, why="Targets follow-up questions to only what's relevant.",
)


def recovery_time_days(scenario: Scenario, amount: Decimal, when: date) -> int | None:
    """Days until the expected balance recovers to its pre-spend level (None if not within horizon)."""
    import dataclasses
    import uuid

    from app.intelligence.projection.planned_projection import OutflowEvent

    effective = max(scenario.today, when)
    extra = OutflowEvent(effective, amount, "hypothetical", uuid.uuid4(), False, 0)
    augmented = dataclasses.replace(scenario, outflows=scenario.outflows + (extra,),
                                    horizon=max(scenario.horizon, effective))
    pre = scenario.current_balance
    for point in project(augmented, ScenarioMode.expected):
        if point.date > scenario.today and point.balance >= pre:
            return (point.date - scenario.today).days
    return None
