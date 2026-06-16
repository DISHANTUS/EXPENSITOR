"""Recommendation bundles (C9) — combined goal-recovery plans.

Greedily combines low-friction levers (savings, then upcoming income, then a
modest cut) until a behind goal's gap is covered. Optimises life, not just money:
no events moved, daily budget preserved. Ranked separately from single recs.
"""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.recommendation.ranking import is_excluded
from app.intelligence.recommendation.recommendation import (
    GOAL_RECOVERY,
    Bundle,
    Recommendation,
    RecommendationContext,
)

# Prefer the least-friction levers first.
_LEVER_PREFERENCE = {"use_savings": 0, "wait_for_income": 1}
_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}


def _contribution(rec: Recommendation) -> Decimal:
    return Decimal(str(rec.evidence.get("estimated_recovery_contribution", "0")))


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def build_bundles(goal_recs: list[Recommendation], ctx: RecommendationContext) -> list[Bundle]:
    bundles: list[Bundle] = []
    for goal in ctx.goals:
        if goal.status != "behind" or goal.shortfall <= 0:
            continue
        levers = [r for r in goal_recs
                  if r.category == GOAL_RECOVERY and r.evidence.get("goal") == goal.name
                  and not is_excluded(r, ctx.excluded_levers)]
        if not levers:
            continue
        levers.sort(key=lambda r: (_LEVER_PREFERENCE.get(r.lever_key, 2), -float(_contribution(r))))

        chosen: list[Recommendation] = []
        total = Decimal("0")
        for r in levers:
            chosen.append(r)
            total += _contribution(r)
            if total >= goal.shortfall:
                break
        covered = total >= goal.shortfall
        effort = max((r.effort_level for r in chosen), key=lambda e: _EFFORT_ORDER.get(e, 1))
        outcome = (
            f"{goal.name} becomes affordable. No planned events need to move, and your daily budget stays within target."
            if covered else
            f"Closes most of the {ph.money(goal.shortfall, ctx.currency)} gap toward {goal.name} without disrupting daily life."
        )
        bundles.append(Bundle(
            bundle_id=f"goal_recovery:{_slug(goal.name)}", title=f"{goal.name} Recovery Plan",
            recommendations=tuple(chosen),
            combined_benefit=f"about {ph.money(total, ctx.currency)} toward {goal.name}",
            combined_effort=effort, combined_risk="low", outcome_preview=outcome,
            score=float(min(Decimal("1"), total / goal.shortfall)),
        ))
    bundles.sort(key=lambda b: -b.score)
    return bundles
