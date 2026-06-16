"""Recommendation ranking (C9): score, dedupe, honour exclusions.

High impact + low effort ranks highest. Excluded levers are dropped (the engine
prefers alternatives); duplicates targeting the same lever are merged (max impact).
"""

from __future__ import annotations

import dataclasses

from app.intelligence.recommendation.recommendation import (
    CONFIDENCE_RANK,
    EFFORT_RANK,
    URGENCY_RANK,
    Recommendation,
)

W_IMPACT, W_URGENCY, W_CONFIDENCE, W_EFFORT = 0.40, 0.25, 0.20, 0.15


def is_excluded(rec: Recommendation, excluded: tuple[str, ...]) -> bool:
    return rec.lever_key in excluded


def score(rec: Recommendation) -> float:
    return (
        W_IMPACT * rec.impact
        + W_URGENCY * URGENCY_RANK.get(rec.urgency, 0.5)
        + W_CONFIDENCE * CONFIDENCE_RANK.get(rec.confidence, 1.0)
        - W_EFFORT * EFFORT_RANK.get(rec.effort_level, 0.5)
    )


def rank(recs: list[Recommendation], excluded: tuple[str, ...] = ()) -> list[Recommendation]:
    kept = [r for r in recs if not is_excluded(r, excluded)]
    # merge duplicates targeting the same lever (keep highest impact)
    by_lever: dict[str, Recommendation] = {}
    for r in kept:
        cur = by_lever.get(r.lever_key)
        if cur is None or r.impact > cur.impact:
            by_lever[r.lever_key] = r
    scored = [dataclasses.replace(r, score=score(r)) for r in by_lever.values()]
    scored.sort(key=lambda r: (-r.score, r.recommendation_id))
    return scored
