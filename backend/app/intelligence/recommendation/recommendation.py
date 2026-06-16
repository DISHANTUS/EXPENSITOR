"""Recommendation Engine (C9) — structured types.

The engine is a deterministic aggregator/ranker over already-computed intelligence
(behavioral insights, savings states, dependencies, advisor view, guidance, risk).
No financial recomputation. Recommendations are OPTIONS, never commands, and are
the single source of truth for Companion / Ollama / preference learning / health.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# Categories
SAVINGS_OPPORTUNITY = "savings_opportunity"
SPENDING_REDUCTION = "spending_reduction"
TIMING_OPPORTUNITY = "timing_opportunity"
DEPENDENCY_RISK = "dependency_risk"
GOAL_RECOVERY = "goal_recovery"
LIFESTYLE_OPTIMIZATION = "lifestyle_optimization"
COMMITMENT_MANAGEMENT = "commitment_management"
BEHAVIORAL_IMPROVEMENT = "behavioral_improvement"

EFFORT_RANK = {"low": 0.2, "medium": 0.5, "high": 0.8}
URGENCY_RANK = {"low": 0.2, "medium": 0.5, "high": 0.85}
CONFIDENCE_RANK = {"low": 0.4, "normal": 1.0, "high": 1.0}


@dataclass(frozen=True)
class LifeImpact:
    improves: str
    daily_change: str
    unchanged: str

    def as_dict(self) -> dict[str, str]:
        return {"improves": self.improves, "daily_change": self.daily_change, "unchanged": self.unchanged}


@dataclass(frozen=True)
class OutcomePreview:
    goal_progress_change: str
    savings_change: str
    dependency_change: str
    risk_change: str
    daily_life_change: str
    projected_result: str

    def as_dict(self) -> dict[str, str]:
        return {
            "goal_progress_change": self.goal_progress_change, "savings_change": self.savings_change,
            "dependency_change": self.dependency_change, "risk_change": self.risk_change,
            "daily_life_change": self.daily_life_change, "projected_result": self.projected_result,
        }


@dataclass(frozen=True)
class Recommendation:
    recommendation_id: str
    category: str
    lever_key: str
    title: str
    action: str
    impact: float                 # 0..1
    reasoning: str
    expected_benefit: str
    effort_level: str             # low | medium | high
    confidence: str               # low | normal
    urgency: str                  # low | medium | high
    consequences_if_ignored: str
    life_impact: LifeImpact
    outcome_preview: OutcomePreview
    score: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)

    def texts(self) -> list[str]:
        return [self.title, self.action, self.reasoning, self.expected_benefit, self.consequences_if_ignored,
                self.life_impact.improves, self.life_impact.daily_change, self.life_impact.unchanged]

    def as_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id, "category": self.category, "lever_key": self.lever_key,
            "title": self.title, "action": self.action, "impact": round(self.impact, 4),
            "reasoning": self.reasoning, "expected_benefit": self.expected_benefit,
            "effort_level": self.effort_level, "confidence": self.confidence, "urgency": self.urgency,
            "consequences_if_ignored": self.consequences_if_ignored, "life_impact": self.life_impact.as_dict(),
            "outcome_preview": self.outcome_preview.as_dict(), "score": round(self.score, 4), "evidence": self.evidence,
        }


@dataclass(frozen=True)
class GoalState:
    kind: str            # monthly_target | custom_goal
    name: str
    status: str          # behind | on_track | met | completed
    shortfall: Decimal
    target_date: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendationContext:
    """Already-computed intelligence the engine maps into recommendations.
    Assembled by recommendation_service; the engine performs no recomputation."""

    currency: str
    behavioral_insights: tuple = ()                  # list[BehavioralInsight]
    goals: tuple[GoalState, ...] = ()
    dependencies: tuple[dict[str, Any], ...] = ()    # Dependency.as_dict()
    advisor_view: dict[str, Any] = field(default_factory=dict)
    recurring_load: dict[str, Any] | None = None     # recurring_cost_load metric facts
    available_savings: Decimal = Decimal("0")
    next_income: dict[str, Any] | None = None        # {"date", "amount"}
    excluded_levers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bundle:
    bundle_id: str
    title: str
    recommendations: tuple[Recommendation, ...]
    combined_benefit: str
    combined_effort: str
    combined_risk: str
    outcome_preview: str
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id, "title": self.title,
            "recommendations": [r.as_dict() for r in self.recommendations],
            "combined_benefit": self.combined_benefit, "combined_effort": self.combined_effort,
            "combined_risk": self.combined_risk, "outcome_preview": self.outcome_preview,
            "score": round(self.score, 4),
        }
