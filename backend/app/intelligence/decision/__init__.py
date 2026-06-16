"""Financial Decision Engine (C7a) — generalized, attribute-based, structured-only.

Answers "I want to do this financially": can I? now? best time? what happens?
how do I afford it? what must I change? — via constraint-respecting strategies.
Pure and deterministic; the Advisor layer renders the prose.
"""

from __future__ import annotations

from app.intelligence.decision.engine import evaluate
from app.intelligence.decision.request import (
    DecisionKind,
    DecisionRequest,
    EmotionalImportance,
    Flexibility,
    OutflowShape,
    UserConstraints,
)
from app.intelligence.decision.result import DecisionResult

__all__ = [
    "evaluate",
    "DecisionKind",
    "DecisionRequest",
    "DecisionResult",
    "EmotionalImportance",
    "Flexibility",
    "OutflowShape",
    "UserConstraints",
]
