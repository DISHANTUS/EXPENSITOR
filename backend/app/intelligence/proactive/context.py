"""Proactive Advisor — the assembled input bundle (already-computed intelligence).

Holds only outputs of existing engines/services. Generators read this; they never
recompute a financial fact (R3 whole-month inputs are all here).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ProactiveContext:
    today: date
    currency: str
    has_history: bool                                  # R4 cold-start gate
    health: dict[str, Any] = field(default_factory=dict)          # HealthScore.as_dict()
    behavioral_memory: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)  # key -> {score,trend,duration,confidence,facts}
    dependencies: tuple[dict[str, Any], ...] = ()
    goals: tuple[dict[str, Any], ...] = ()             # {kind, name, status, shortfall}
    goal_sacrifice: dict[str, Any] | None = None
    next_income: dict[str, Any] | None = None          # {amount, currency, date, window, exact}
    recommendations: tuple[dict[str, Any], ...] = ()   # policy-ranked (excluded already removed)
    excluded_levers: tuple[str, ...] = ()              # R2 double-guard
