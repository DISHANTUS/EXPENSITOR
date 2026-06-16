"""Recommendation Engine (C9) — pure aggregator/ranker over a RecommendationContext.

No financial recomputation; maps already-computed intelligence into ranked
recommendations + bundles, honouring per-request lever exclusions.
"""

from __future__ import annotations

from typing import Any

from app.intelligence.recommendation import bundles as bundle_mod
from app.intelligence.recommendation import ranking, sources
from app.intelligence.recommendation.recommendation import GOAL_RECOVERY, RecommendationContext


def build_recommendations(ctx: RecommendationContext) -> dict[str, Any]:
    raw = sources.all_sources(ctx)
    alternatives_applied = any(ranking.is_excluded(r, ctx.excluded_levers) for r in raw)

    ranked = ranking.rank(raw, ctx.excluded_levers)
    goal_recs = [r for r in raw if r.category == GOAL_RECOVERY and not ranking.is_excluded(r, ctx.excluded_levers)]
    bundles = bundle_mod.build_bundles(goal_recs, ctx)

    return {
        "recommendations": ranked,
        "bundles": bundles,
        "excluded_levers": list(ctx.excluded_levers),
        "alternatives_applied": alternatives_applied,
    }
