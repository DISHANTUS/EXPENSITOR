"""Recommendation ranking (C9 + C7b policy): score, dedupe, apply policy.

High impact + low effort ranks highest. Policy affects ORDERING only:
  * strong-excluded levers are removed (unless force-included)
  * soft-excluded levers are kept but heavily down-ranked
  * preferred levers get an acceptance-rate boost
It never changes any financial fact. Returns the ranked list + a transparent
policy_influence breakdown so personalization is never hidden.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.intelligence.recommendation.recommendation import (
    CONFIDENCE_RANK,
    EFFORT_RANK,
    URGENCY_RANK,
    Recommendation,
)

W_IMPACT, W_URGENCY, W_CONFIDENCE, W_EFFORT = 0.40, 0.25, 0.20, 0.15
SOFT_DOWNRANK = 0.25


def is_excluded(rec: Recommendation, excluded) -> bool:
    return rec.lever_key in set(excluded)


def base_score(rec: Recommendation) -> float:
    return (
        W_IMPACT * rec.impact
        + W_URGENCY * URGENCY_RANK.get(rec.urgency, 0.5)
        + W_CONFIDENCE * CONFIDENCE_RANK.get(rec.confidence, 1.0)
        - W_EFFORT * EFFORT_RANK.get(rec.effort_level, 0.5)
    )


def rank(
    recs: list[Recommendation], *, strong_excluded: set[str] = frozenset(),
    soft_excluded: set[str] = frozenset(), boosts: dict[str, float] | None = None,
    include_levers: set[str] = frozenset(),
) -> tuple[list[Recommendation], dict[str, Any]]:
    boosts = boosts or {}
    influence: dict[str, list[str]] = {"excluded_by_policy": [], "boosted_by_policy": [], "deprioritized_by_policy": []}

    # merge duplicates targeting the same lever (keep highest impact)
    by_lever: dict[str, Recommendation] = {}
    for r in recs:
        cur = by_lever.get(r.lever_key)
        if cur is None or r.impact > cur.impact:
            by_lever[r.lever_key] = r

    ranked: list[Recommendation] = []
    for lever, r in by_lever.items():
        if lever in strong_excluded and lever not in include_levers:
            influence["excluded_by_policy"].append(lever)
            continue
        score = base_score(r)
        if lever in boosts:
            score += boosts[lever]
            influence["boosted_by_policy"].append(lever)
        if lever in soft_excluded:
            score *= SOFT_DOWNRANK
            influence["deprioritized_by_policy"].append(lever)
        ranked.append(dataclasses.replace(r, score=score))

    ranked.sort(key=lambda r: (-r.score, r.recommendation_id))
    return ranked, influence
