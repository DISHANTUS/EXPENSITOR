"""Behavioral Intelligence — the BehavioralProfile and its read-only projections.

The profile is the *foundation of the Financial Advisor Brain*: one computed
object that six consumers read through stable projections, with no redesign:

    insights_payload()   -> Companion (B2)
    advisor_view()       -> Purchase / Financial Decision Engine (C7)
    signals()            -> Recommendation Engine (C9)
    dimensions/composite -> Financial Health Score (C8)
    personality_inputs() -> Personality Engine (C10, stub)
    to_facts()           -> Ollama narration (C5) grounding

All values are deterministic, confidence-scored, and derived from stored data.
This module is a pure data container; scoring.py builds it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

FACTS_SCHEMA_VERSION = 1

# Score banding (tunable; centralised here for all layers).
STRONG_SCORE = 75
WEAK_SCORE = 40
OPPORTUNITY_LOW, OPPORTUNITY_HIGH = 40, 70


@dataclass(frozen=True)
class BehavioralMetric:
    key: str
    dimension: str
    value: Decimal | None       # raw metric value (None when uncomputable)
    score: int                  # 0-100, higher = healthier (50 = neutral/low-conf)
    label: str                  # good | watch | concern | insufficient_data | <reason>
    trend: str                  # improving | flat | worsening | unknown
    confidence: str             # low | normal
    facts: dict[str, Any] = field(default_factory=dict)

    def as_facts(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "dimension": self.dimension,
            "value": (str(self.value) if self.value is not None else None),
            "score": self.score,
            "label": self.label,
            "trend": self.trend,
            "confidence": self.confidence,
            "facts": self.facts,
        }


@dataclass(frozen=True)
class BehavioralDimension:
    name: str
    score: int
    confidence: str
    metric_keys: tuple[str, ...]


@dataclass(frozen=True)
class SworItem:
    """A strength / weakness / opportunity / risk — derived deterministically."""

    metric_key: str
    dimension: str
    statement: str
    level: str          # strong | mild  (strengths)  |  high | moderate (weaknesses/risks)
    score: int
    trend: str
    confidence: str


@dataclass(frozen=True)
class RecommendationSignal:
    """Machine-readable signal for the future Recommendation Engine (C9)."""

    key: str             # category name or metric key
    issue: str           # overspending | declining | volatility | threshold_pressure | underuse ...
    severity: str        # low | medium | high
    impact: float        # 0..1 normalised magnitude
    confidence: str      # low | normal
    direction: str       # improving | flat | worsening | unknown
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "issue": self.issue,
            "severity": self.severity,
            "impact": round(self.impact, 4),
            "confidence": self.confidence,
            "direction": self.direction,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class BehavioralProfile:
    today: date
    base_currency: str
    window: dict[str, Any]
    composite_score: int
    confidence: str
    metrics: tuple[BehavioralMetric, ...]
    dimensions: dict[str, BehavioralDimension]
    strengths: tuple[SworItem, ...]
    weaknesses: tuple[SworItem, ...]
    opportunities: tuple[SworItem, ...]
    risks: tuple[SworItem, ...]
    recommendation_signals: tuple[RecommendationSignal, ...]
    advisor: dict[str, Any]  # precomputed advisor views (categories, periods, ...)

    # ----- lookups -----
    def metric(self, key: str) -> BehavioralMetric | None:
        return next((m for m in self.metrics if m.key == key), None)

    # ----- consumer projections (stable contracts) -----
    def signals(self) -> list[dict[str, Any]]:
        """C9 Recommendation Engine: flat machine-readable signal list."""
        return [s.as_dict() for s in self.recommendation_signals]

    def advisor_view(self) -> dict[str, Any]:
        """C7 Financial Decision Engine: which categories to cut, impulse periods, etc."""
        return self.advisor

    def personality_inputs(self) -> dict[str, Any]:
        """C10 Personality Engine (stub): dimension vector + tagged metric scores."""
        return {
            "dimensions": {name: dim.score for name, dim in self.dimensions.items()},
            "metrics": {m.key: m.score for m in self.metrics},
            "confidence": self.confidence,
        }

    def insights_payload(self) -> dict[str, Any]:
        """B2 Companion: the SWOR lists shaped for feed generation."""
        return {
            "strengths": [_swor(s) for s in self.strengths],
            "weaknesses": [_swor(s) for s in self.weaknesses],
            "opportunities": [_swor(s) for s in self.opportunities],
            "risks": [_swor(s) for s in self.risks],
        }

    def to_facts(self, schema_version: int = FACTS_SCHEMA_VERSION) -> dict[str, Any]:
        """C5 Ollama grounding payload. The ONLY thing a narrator ever sees."""
        return {
            "schema_version": schema_version,
            "today": self.today.isoformat(),
            "currency": self.base_currency,
            "window": self.window,
            "composite_score": self.composite_score,
            "confidence": self.confidence,
            "dimensions": {
                name: {"score": dim.score, "confidence": dim.confidence}
                for name, dim in self.dimensions.items()
            },
            "metrics": [m.as_facts() for m in self.metrics],
            "strengths": [_swor(s) for s in self.strengths],
            "weaknesses": [_swor(s) for s in self.weaknesses],
            "opportunities": [_swor(s) for s in self.opportunities],
            "risks": [_swor(s) for s in self.risks],
            "signals": self.signals(),
            "advisor": self.advisor,
        }


def _swor(s: SworItem) -> dict[str, Any]:
    return {
        "metric_key": s.metric_key,
        "dimension": s.dimension,
        "statement": s.statement,
        "level": s.level,
        "score": s.score,
        "trend": s.trend,
        "confidence": s.confidence,
    }
