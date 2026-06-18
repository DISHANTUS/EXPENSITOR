"""Budget feasibility (Budget Intelligence System — Phase 3).

Never binary "possible/impossible". A waterfall (Income → Essential Living →
Housing → Committed → Emergency Buffer → Goals → Lifestyle), a success-probability
band with the reasoning, and structural diagnosis (housing/transport/subscription
ratios) — because the diagnosis matters more than the number.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class WaterfallStep(BaseModel):
    label: str
    amount: Decimal
    running_remaining: Decimal   # what's left after this step is funded


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
    emergency_buffer: Decimal          # first-class, funded before goals
    lifestyle_total: Decimal
    comfortable_surplus: Decimal       # income − essentials − buffer − lifestyle (keep lifestyle)
    stretch_surplus: Decimal           # income − essentials − buffer (cut all lifestyle)

    waterfall: list[WaterfallStep]
    goals: list[GoalFeasibility]
    overall_band: str
    structural_flags: list[StructuralFlag]
    anomalies: list[str]               # recent actual spend vs your usual / profile estimate
    summary: str
