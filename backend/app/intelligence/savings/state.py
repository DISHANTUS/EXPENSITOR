"""Savings engine — structured state types (pure, no prose)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class MonthlyTargetState:
    base_target: Decimal
    effective_target: Decimal          # base + carried/distribute share (derived; base never mutated)
    net_so_far: Decimal
    projected_net: Decimal
    status: str                        # met | on_track | behind
    shortfall: Decimal
    progress: Decimal                  # net_so_far / effective_target

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_target": str(self.base_target),
            "effective_target": str(self.effective_target),
            "net_so_far": str(self.net_so_far),
            "projected_net": str(self.projected_net),
            "status": self.status,
            "shortfall": str(self.shortfall),
            "progress": str(self.progress),
        }


@dataclass(frozen=True)
class CustomGoalState:
    target_amount: Decimal
    target_date: date | None
    progress: Decimal                  # share of target currently held
    projected_completion_date: date | None
    feasible: bool
    confidence: str
    required_daily_saving: Decimal
    required_weekly_saving: Decimal
    required_monthly_saving: Decimal
    status: str                        # completed | on_track | behind
    shortfall: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_amount": str(self.target_amount),
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "progress": str(self.progress),
            "projected_completion_date": self.projected_completion_date.isoformat() if self.projected_completion_date else None,
            "feasible": self.feasible,
            "confidence": self.confidence,
            "required_daily_saving": str(self.required_daily_saving),
            "required_weekly_saving": str(self.required_weekly_saving),
            "required_monthly_saving": str(self.required_monthly_saving),
            "status": self.status,
            "shortfall": str(self.shortfall),
        }


@dataclass(frozen=True)
class RecoveryOption:
    choice: str                        # keep_unchanged | distribute | new_plan
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"choice": self.choice, "data": self.data}


@dataclass(frozen=True)
class SavingsReasons:
    """Why a target is at risk — sourced from structured facts only."""

    expenses: tuple[dict[str, Any], ...] = ()       # top contributing categories
    decisions: tuple[dict[str, Any], ...] = ()      # upcoming planned outflows in the window
    opportunities: tuple[dict[str, Any], ...] = ()  # categories the user could trim

    def as_dict(self) -> dict[str, Any]:
        return {"expenses": list(self.expenses), "decisions": list(self.decisions),
                "opportunities": list(self.opportunities)}
