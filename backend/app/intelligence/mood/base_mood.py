"""Base-mood selection (Sprint 4c-A, pure).

Maps the user's ongoing financial state to the resting face, with explainable
reasons. Weather-proofed: the worst outcome is 'concerned', never anger/sadness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class MoodContext:
    has_data: bool
    total_spent: Decimal
    saved: Decimal
    red_days: int
    crown_days: int
    monthly_threshold: Decimal | None
    has_active_goal: bool
    overdue_loans: int


@dataclass(frozen=True)
class BaseMood:
    mood_id: str
    reasons: list[dict[str, str]] = field(default_factory=list)   # {label, value}


def select_base(ctx: MoodContext) -> BaseMood:
    reasons: list[dict[str, str]] = []

    if not ctx.has_data:
        return BaseMood("neutral", [{"label": "Getting to know you", "value": "not much history yet"}])

    over_pct = None
    if ctx.monthly_threshold and ctx.monthly_threshold > 0:
        over_pct = (ctx.total_spent - ctx.monthly_threshold) / ctx.monthly_threshold * 100

    if ctx.red_days:
        reasons.append({"label": "Red days", "value": str(ctx.red_days)})
    if ctx.overdue_loans:
        reasons.append({"label": "Overdue loans", "value": str(ctx.overdue_loans)})

    # WAY over budget OR a clearly strained month -> concerned (the floor).
    if over_pct is not None and over_pct >= 10:
        reasons.insert(0, {"label": "Budget exceeded", "value": f"{over_pct:.0f}%"})
        return BaseMood("concerned", reasons)
    if ctx.overdue_loans and ctx.red_days >= 3:
        return BaseMood("concerned", reasons)

    if over_pct is not None and over_pct > 0:
        reasons.insert(0, {"label": "Budget exceeded", "value": f"{over_pct:.0f}%"})
        return BaseMood("slightly_over", reasons)

    if ctx.saved > 0 and ctx.crown_days >= 1 and ctx.red_days == 0:
        reasons.insert(0, {"label": "Saved this month", "value": f"{ctx.saved}"})
        return BaseMood("saving_well", reasons)
    if ctx.has_active_goal and ctx.saved > 0:
        reasons.insert(0, {"label": "Progressing toward a goal", "value": "yes"})
        return BaseMood("goal_progress", reasons)
    if ctx.red_days == 0 and ctx.total_spent > 0:
        return BaseMood("on_budget", [{"label": "Within budget so far", "value": "yes"}, *reasons])

    return BaseMood("neutral", reasons)
