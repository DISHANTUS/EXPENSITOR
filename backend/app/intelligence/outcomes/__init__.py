"""Outcome Tracking & Adaptive Planning (Phase E) — deterministic, evidence-only.

Outcomes influence ordering / ranking / confidence / annotations / adaptive
planning ONLY. They never modify affordability, projections, risk, health-score
math, goals, plans, budgets, expenses, savings math, or decision-engine facts.
Distinguishes effectiveness from circumstance (E7); no ML, no LLM.
"""

from __future__ import annotations

from app.intelligence.outcomes import types
from app.intelligence.outcomes.adaptive import build_plan
from app.intelligence.outcomes.effectiveness import LeverEffectiveness, build_effectiveness
from app.intelligence.outcomes.types import classify_circumstance, decay_weight, trust_level

__all__ = [
    "types", "build_plan", "LeverEffectiveness", "build_effectiveness",
    "classify_circumstance", "decay_weight", "trust_level",
]
