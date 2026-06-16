"""Behavioral Intelligence — metric registry.

Adding a metric = write one ``compute(data) -> BehavioralMetric`` function and
decorate it with ``@register(...)``. Every higher layer (dimensions, composite,
SWOR, signals, advisor_view, personality_inputs) reads these specs + their
metadata generically — there is no per-metric branching anywhere else.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# --- Dimensions (the 6 pillars of the advisor brain) ---
DISCIPLINE = "spending_discipline"
PLANNING = "planning_adherence"
CASHFLOW = "cashflow_health"
SAVINGS = "savings_resilience"
LIFESTYLE = "lifestyle_profile"
INCOME = "income_quality"

DIMENSION_ORDER = (DISCIPLINE, PLANNING, CASHFLOW, SAVINGS, LIFESTYLE, INCOME)

# Composite weights (sum need not be 1; normalised over *available* dimensions).
DIMENSION_WEIGHTS = {
    DISCIPLINE: 0.25,
    PLANNING: 0.20,
    CASHFLOW: 0.20,
    SAVINGS: 0.20,
    LIFESTYLE: 0.10,
    INCOME: 0.05,
}

# --- Metric directions ---
HIGHER_BETTER = "higher_is_better"
LOWER_BETTER = "lower_is_better"
DESCRIPTIVE = "descriptive"

# Personality archetypes a metric can inform (C10, documented only).
ARCHETYPES = (
    "conservative_saver",
    "financial_planner",
    "balanced",
    "experience_seeker",
    "social_spender",
    "impulse_buyer",
    "risk_taker",
)


@dataclass(frozen=True)
class MetricSpec:
    key: str
    dimension: str
    direction: str
    controllable: bool          # user can act on it -> feeds opportunities[]
    forward_risk: bool          # worsening trend implies future harm -> feeds risks[]
    compute: Callable           # (BehaviorData) -> BehavioralMetric
    personality_tags: tuple[str, ...] = field(default_factory=tuple)


# Insertion-ordered registry (Python dicts preserve order).
METRIC_REGISTRY: dict[str, MetricSpec] = {}


def register(
    *,
    key: str,
    dimension: str,
    direction: str,
    controllable: bool = False,
    forward_risk: bool = False,
    personality_tags: tuple[str, ...] = (),
) -> Callable[[Callable], Callable]:
    def _decorator(fn: Callable) -> Callable:
        if key in METRIC_REGISTRY:
            raise ValueError(f"Duplicate behavioral metric key: {key}")
        METRIC_REGISTRY[key] = MetricSpec(
            key=key,
            dimension=dimension,
            direction=direction,
            controllable=controllable,
            forward_risk=forward_risk,
            compute=fn,
            personality_tags=personality_tags,
        )
        return fn

    return _decorator
