"""Recommendation Engine (C9) — the bridge from intelligence to prioritized action.

Reusable source of truth for Companion / Ollama / preference learning / health /
adaptive planning. Deterministic aggregator + ranker; no recomputation, no LLM.
"""

from __future__ import annotations

from app.intelligence.recommendation.engine import build_recommendations
from app.intelligence.recommendation.recommendation import (
    Bundle,
    GoalState,
    Recommendation,
    RecommendationContext,
)

__all__ = ["build_recommendations", "Bundle", "GoalState", "Recommendation", "RecommendationContext"]
