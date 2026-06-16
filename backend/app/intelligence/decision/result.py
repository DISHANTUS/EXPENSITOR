"""Financial Decision Engine — structured result types (C7a). No prose here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.intelligence.decision.attributes import DecisionAttributes


@dataclass(frozen=True)
class FundingPart:
    source: str          # immediate_balance | savings_reserve | future_income | daily_savings
    amount: Decimal
    ref: str | None = None   # e.g. income date / category

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.source, "amount": str(self.amount), "ref": self.ref}


@dataclass(frozen=True)
class StrategyTradeoffs:
    harder: tuple[str, ...] = ()
    easier: tuple[str, ...] = ()
    delayed: tuple[str, ...] = ()
    unaffected: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"harder": list(self.harder), "easier": list(self.easier),
                "delayed": list(self.delayed), "unaffected": list(self.unaffected)}


@dataclass(frozen=True)
class DecisionStrategy:
    strategy_id: str
    strategy_kind: str
    purchase_date: date
    feasible: bool
    score: int
    impact_level: str                 # none | minor | moderate | significant
    funding: tuple[FundingPart, ...] = ()
    savings_used: Decimal = Decimal("0")
    income_events_used: tuple[dict[str, Any], ...] = ()
    expenses_to_reduce: tuple[dict[str, Any], ...] = ()
    daily_saving_required: Decimal = Decimal("0")
    saving_days: int = 0
    balance_after: dict[str, str] = field(default_factory=dict)   # worst/expected
    safe_daily_before: Decimal = Decimal("0")
    safe_daily_after: Decimal = Decimal("0")
    risk_before: str = "none"
    risk_after: str = "none"
    assumptions: tuple[str, ...] = ()
    tradeoffs: StrategyTradeoffs = field(default_factory=StrategyTradeoffs)
    constraints_used: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_kind": self.strategy_kind,
            "purchase_date": self.purchase_date.isoformat(),
            "feasible": self.feasible,
            "score": self.score,
            "impact_level": self.impact_level,
            "funding": [f.as_dict() for f in self.funding],
            "savings_used": str(self.savings_used),
            "income_events_used": list(self.income_events_used),
            "expenses_to_reduce": list(self.expenses_to_reduce),
            "daily_saving_required": str(self.daily_saving_required),
            "saving_days": self.saving_days,
            "balance_after": self.balance_after,
            "safe_daily_before": str(self.safe_daily_before),
            "safe_daily_after": str(self.safe_daily_after),
            "risk_before": self.risk_before,
            "risk_after": self.risk_after,
            "assumptions": list(self.assumptions),
            "tradeoffs": self.tradeoffs.as_dict(),
            "constraints_used": list(self.constraints_used),
        }


@dataclass(frozen=True)
class ImpactSummary:
    daily_budget_after: Decimal
    weekly_budget_after: Decimal
    monthly_remaining_after: Decimal | None
    savings_progress_after: Decimal | None
    days_until_recovery: int | None
    impact_level: str                 # none | minor | moderate | significant

    def as_dict(self) -> dict[str, Any]:
        monthly = self.monthly_remaining_after
        progress = self.savings_progress_after
        return {
            "daily_budget_after": str(self.daily_budget_after),
            "weekly_budget_after": str(self.weekly_budget_after),
            "monthly_remaining_after": str(monthly) if monthly is not None else None,
            "savings_progress_after": str(progress) if progress is not None else None,
            "days_until_recovery": self.days_until_recovery,
            "impact_level": self.impact_level,
        }


@dataclass(frozen=True)
class DecisionResult:
    item_label: str
    amount_base: Decimal
    currency: str
    attributes: DecisionAttributes
    can_do_now: bool
    verdict: str                      # affordable | tight | not_now
    now_consequence: dict[str, Any]
    best_strategy: DecisionStrategy | None
    strategies: tuple[DecisionStrategy, ...]
    impact: ImpactSummary
    dependencies: tuple[dict[str, Any], ...] = ()   # future hook (dependency analysis)

    def to_facts(self) -> dict[str, Any]:
        return {
            "item_label": self.item_label,
            "amount": str(self.amount_base),
            "currency": self.currency,
            "attributes": self.attributes.as_dict(),
            "can_do_now": self.can_do_now,
            "verdict": self.verdict,
            "now_consequence": self.now_consequence,
            "best_strategy": self.best_strategy.as_dict() if self.best_strategy else None,
            "strategies": [s.as_dict() for s in self.strategies],
            "impact": self.impact.as_dict(),
            "dependencies": list(self.dependencies),
        }
