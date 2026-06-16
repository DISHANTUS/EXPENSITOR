"""C8 — Financial Health Score: a pure aggregator over the BehavioralProfile.

Multi-dimensional, fact-backed, confidence- and stability-aware. Creates no new
intelligence and no financial math; every number traces to an existing metric.
"""

from __future__ import annotations

from app.intelligence.health.score import (
    METRIC_PILLAR,
    PILLAR_ORDER,
    PILLAR_WEIGHTS,
    HealthPillar,
    HealthScore,
    build_health_score,
)

__all__ = [
    "METRIC_PILLAR", "PILLAR_ORDER", "PILLAR_WEIGHTS",
    "HealthPillar", "HealthScore", "build_health_score",
]
