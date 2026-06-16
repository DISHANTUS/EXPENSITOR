"""Recommendation Engine (C9 + C7b) — pure aggregator/ranker over a context.

No financial recomputation; maps already-computed intelligence into ranked
recommendations + bundles, applying the user's policy to ORDERING only (strong
exclude / soft down-rank / preference boost) and reporting policy_influence.
"""

from __future__ import annotations

from typing import Any

from app.intelligence.recommendation import bundles as bundle_mod
from app.intelligence.recommendation import ranking, sources
from app.intelligence.recommendation.recommendation import GOAL_RECOVERY, RecommendationContext


def build_recommendations(ctx: RecommendationContext) -> dict[str, Any]:
    raw = sources.all_sources(ctx)
    strong = set(ctx.excluded_levers)
    alternatives_applied = any(r.lever_key in strong for r in raw)

    ranked, influence = ranking.rank(
        raw, strong_excluded=strong, soft_excluded=set(ctx.soft_excluded_levers),
        boosts=ctx.boosts, include_levers=set(ctx.include_levers),
    )
    goal_recs = [r for r in raw if r.category == GOAL_RECOVERY and not ranking.is_excluded(r, strong)]
    bundles = bundle_mod.build_bundles(goal_recs, ctx)

    return {
        "recommendations": ranked,
        "bundles": bundles,
        "excluded_levers": list(ctx.excluded_levers),
        "alternatives_applied": alternatives_applied,
        "policy_influence": influence,
    }
