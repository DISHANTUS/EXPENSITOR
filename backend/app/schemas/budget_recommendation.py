"""Budget recommendations (Budget Intelligence System — Phase 4).

Problem → diagnosis → recommendation → action. Never one recommendation: a
Conservative / Balanced / Aggressive set the user chooses from. Every change shows
current→suggested (daily AND monthly), monthly impact, a reason, and confidence —
the user never does mental math. Essentials are protected; when cuts can't close
the gap we suggest growing income and explain honestly why a target is unrealistic.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class RecommendationLine(BaseModel):
    label: str                       # "Reduce eating out", "Cancel Netflix"
    current_monthly: Decimal
    suggested_monthly: Decimal
    current_daily: Decimal | None = None      # shown for per-day spends (food/fun)
    suggested_daily: Decimal | None = None
    monthly_impact: Decimal          # +X/month freed
    reason: str
    confidence: str                  # high | medium | low
    protected: bool = False          # touches an essential (only when user insists)


class RecommendationTier(BaseModel):
    style: str                       # conservative | balanced | aggressive
    title: str
    total_monthly_impact: Decimal
    reaches_goal: bool
    confidence: str                  # high | medium | low
    difficulty: str                  # easy | moderate | hard
    changes: list[RecommendationLine]


class GrowIncomeSuggestion(BaseModel):
    label: str
    detail: str
    confidence: str


class RecommendationSet(BaseModel):
    base_currency: str
    target_monthly: Decimal | None
    comfortable_surplus: Decimal
    gap_monthly: Decimal             # extra needed beyond what's comfortably available (0 ⇒ on track)
    on_track: bool
    tiers: list[RecommendationTier]
    grow_income: list[GrowIncomeSuggestion]
    why_not: str | None = None       # honest explanation when even aggressive can't reach
    essential_protection_note: str | None = None
    summary: str
