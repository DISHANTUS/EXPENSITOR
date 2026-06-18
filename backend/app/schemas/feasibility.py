"""Budget feasibility (Budget Intelligence System — Phase 3).

Never binary "possible/impossible". A waterfall (Income → Essential Living →
Housing → Committed → Goals → Lifestyle → Backup Money), a success-probability
band with the reasoning, and structural diagnosis (housing/transport/subscription
ratios) — because the diagnosis matters more than the number. Backup Money is the
LEFTOVER at the very end (only when surplus remains) — never a forced cut that
competes with goals.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class WaterfallSubItem(BaseModel):
    label: str
    amount: Decimal


class WaterfallStep(BaseModel):
    label: str
    amount: Decimal
    running_remaining: Decimal   # what's left after this step is funded
    breakdown: list[WaterfallSubItem] = []   # traceable lines (e.g. Essential living → food/transport)


class StructuralFlag(BaseModel):
    kind: str          # housing_ratio | transport_ratio | subscription_ratio
    ratio: float       # 0..1 share of income
    severity: str      # ok | elevated | high
    message: str


class GoalFeasibility(BaseModel):
    goal: str
    target_monthly: Decimal
    probability_band: str    # very_high | high | medium | low | very_low
    probability_score: int   # 0..100
    reason: str              # full math, concrete numbers


class Feasibility(BaseModel):
    base_currency: str
    optimization_style: str

    income_total: Decimal
    essentials_total: Decimal          # protected + committed
    backup_money: Decimal              # leftover AFTER goals + lifestyle (0 when no surplus)
    lifestyle_total: Decimal
    comfortable_surplus: Decimal       # income − essentials − lifestyle (keep lifestyle)
    stretch_surplus: Decimal           # income − essentials (cut all lifestyle)

    waterfall: list[WaterfallStep]
    goals: list[GoalFeasibility]
    overall_band: str
    structural_flags: list[StructuralFlag]
    anomalies: list[str]               # recent actual spend vs your usual / profile estimate
    summary: str
