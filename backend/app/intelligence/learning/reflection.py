"""Reflection intelligence (Sprint 4b-5b, pure).

Turns a detected change/win into an importance-gated, fixed-option reflection
("what helped most?") whose answer becomes a life lesson. Importance gating
prevents reflection fatigue: we only ask about things that matter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HIGH, MEDIUM, LOW = "high", "medium", "low"

# trigger -> importance (req 4: no fatigue).
_IMPORTANCE = {
    "goal_progress": HIGH,
    "loan_repayment": HIGH,
    "budget_streak": HIGH,
    "savings_milestone": HIGH,
    "food_improvement": MEDIUM,
    "subscription_reduction": MEDIUM,
    "single_purchase": LOW,
    "red_day": LOW,
}


@dataclass(frozen=True)
class ReflectionPrompt:
    trigger: str
    importance: str
    question: str
    options: list[tuple[str, str]] = field(default_factory=list)   # (label, value)


def importance_for(trigger: str) -> str:
    return _IMPORTANCE.get(trigger, MEDIUM)


def should_surface(trigger: str) -> bool:
    return importance_for(trigger) in (HIGH, MEDIUM)


_IMPROVED_OPTIONS = [
    ("Better planning", "better_planning"),
    ("Less food spending", "less_food"),
    ("More income", "more_income"),
    ("Something else", "other"),
]
_STREAK_OPTIONS = [
    ("Sticking to a routine", "routine"),
    ("Cutting one big cost", "cut_cost"),
    ("Automatic saving", "automatic"),
    ("Something else", "other"),
]


def improvement_prompt(saved_more_text: str) -> ReflectionPrompt:
    return ReflectionPrompt(
        trigger="goal_progress", importance=HIGH,
        question=f"{saved_more_text} What helped most?", options=_IMPROVED_OPTIONS,
    )


def success_prompt(win_text: str) -> ReflectionPrompt:
    return ReflectionPrompt(
        trigger="savings_milestone", importance=HIGH,
        question=f"{win_text} What helped you stay consistent?", options=_STREAK_OPTIONS,
    )


# Reflection answer -> the lesson it teaches (positive, reusable).
_ANSWER_LESSON = {
    "better_planning": ("planning", "Planning ahead has worked well for you — keep doing it."),
    "less_food": ("food", "Cutting food spending has worked well for you before."),
    "more_income": ("income_timing", "Extra income months have boosted your savings before."),
    "routine": ("planning", "A steady routine has kept you consistent before."),
    "cut_cost": ("subscriptions", "Cutting one big recurring cost has helped you before."),
    "automatic": ("planning", "Automatic saving has kept you on track before."),
}


def lesson_from_answer(value: str) -> tuple[str, str] | None:
    """(category, canonical lesson) for a positive reflection answer, or None."""
    return _ANSWER_LESSON.get(value)
