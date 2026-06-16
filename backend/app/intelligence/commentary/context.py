"""Commentary Layer (C5) — the single input bundle.

`CommentaryContext` is the one structure every surface (Companion, Recommendations,
Assistant, future Ollama) hands to the renderer. It holds ONLY already-computed
outputs of existing engines — the commentary layer never recomputes a financial
fact. All fields are optional so each caller fills what it has.

Triggers shape the lead/ordering; reserved fields (A10) let C8/B1.5 plug in later
without a redesign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# triggers — what occasioned the commentary (shapes the lead + most-useful-number)
DAILY_BRIEF = "daily_brief"
AFTER_ACTION = "after_action"
ACTION_PREVIEW = "action_preview"
RECOMMENDATIONS = "recommendations"
GOAL_REVIEW = "goal_review"
DECISION = "decision"
DEPENDENCY_ALERT = "dependency_alert"


@dataclass(frozen=True)
class ActionPreview:
    """A6 — a before-confirmation preview: what would change / stay the same /
    important consequence. Assembled by the caller from engine facts only."""

    summary: str                       # "Moving the outing to Jul 18"
    would_change: str                  # "would avoid the current cash-flow pressure"
    would_stay_same: str               # "the budget stays the same — only the date changes"
    consequence: str | None = None     # any important downstream effect

    def as_dict(self) -> dict[str, Any]:
        return {"summary": self.summary, "would_change": self.would_change,
                "would_stay_same": self.would_stay_same, "consequence": self.consequence}


@dataclass(frozen=True)
class CommentaryContext:
    currency: str
    trigger: str
    confidence: str = "normal"               # behavioral confidence (global hedge, A-req8)
    has_history: bool = True                 # A9 cold-start switch
    headline_hint: str | None = None         # e.g. the assistant action summary
    context: dict[str, Any] = field(default_factory=dict)        # LifeEasierContext.as_dict()
    explanations: tuple[dict[str, Any], ...] = ()                # AdvisorExplanation.as_dict()
    behavioral_insights: tuple[dict[str, Any], ...] = ()         # BehavioralInsight.as_dict()
    recommendations: tuple[dict[str, Any], ...] = ()             # Recommendation.as_dict()
    bundles: tuple[dict[str, Any], ...] = ()
    dependencies: tuple[dict[str, Any], ...] = ()                # Dependency.as_dict() (+ enriched label/time)
    goals: tuple[dict[str, Any], ...] = ()                       # {kind, name, status, shortfall, ...}
    next_income: dict[str, Any] | None = None                   # {amount, currency, date, window, exact, source_label}
    risk: dict[str, Any] | None = None                          # {risk_level, min_expected_balance, date}
    policy_influence: dict[str, Any] = field(default_factory=dict)   # {excluded, boosted, deprioritized}
    alternatives_applied: bool = False                          # a preference excluded an option (A4/A7)
    policy_provenance: dict[str, Any] = field(default_factory=dict)  # lever -> {reason, reason_context} (A8)
    protect_emotional: bool = False                             # policy flag (A4)
    action_preview: ActionPreview | None = None                 # A6

    # --- A10 reserved extension points (renderer ignores until populated) ---
    alerts: tuple[dict[str, Any], ...] = ()                     # future notification alerts
    reminders: tuple[dict[str, Any], ...] = ()                  # future scheduler reminders
    health_score: dict[str, Any] | None = None                 # future C8 financial health score
    extra_metrics: dict[str, Any] = field(default_factory=dict) # future B1.5 metrics
