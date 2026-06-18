"""Success / achievement detection (Sprint 4b-5b, pure).

Most finance apps only remember failures. EXPENSITOR remembers wins — but only
achievement-worthy ones (a single crown day is NOT an achievement). Importance
feeds the recap, future timeline, and mood engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# AchievementType values (kept as strings to stay import-light).
FIRST_SALARY = "first_salary"
GOAL_COMPLETED = "goal_completed"
DEBT_CLEARED = "debt_cleared"
GOAL_MILESTONE = "goal_milestone"
SAVINGS_STREAK = "savings_streak"
LOAN_REPAID = "loan_repaid"

# importance reuses ImportanceLevel vocabulary.
LIFE_MILESTONE, HIGH, MEDIUM = "life_milestone", "high", "medium"


@dataclass(frozen=True)
class Achievement:
    type: str
    importance: str
    label: str
    when: date | None = None


def detect(
    *,
    completed_goals: list[tuple[str, date | None]] | None = None,
    streak_months: int = 0,
    repaid_loans: list[tuple[str, date | None]] | None = None,
    first_salary: date | None = None,
    goal_milestones: list[tuple[str, int, date | None]] | None = None,
    today: date | None = None,
) -> list[Achievement]:
    out: list[Achievement] = []

    if first_salary is not None:
        out.append(Achievement(FIRST_SALARY, LIFE_MILESTONE, "Recorded your first income", first_salary))

    for name, when in completed_goals or []:
        out.append(Achievement(GOAL_COMPLETED, LIFE_MILESTONE, f"Completed your {name} goal", when))

    for name, when in repaid_loans or []:
        out.append(Achievement(LOAN_REPAID, MEDIUM, f"{name} repaid what they owed", when))

    # Savings streak only counts once it's genuinely sustained.
    if streak_months >= 6:
        out.append(Achievement(SAVINGS_STREAK, HIGH, f"Hit your savings target {streak_months} months running"))
    elif streak_months >= 3:
        out.append(Achievement(SAVINGS_STREAK, MEDIUM, f"Hit your savings target {streak_months} months running"))

    # Milestones only at >=50% (25% would be noise).
    for name, pct, when in goal_milestones or []:
        if pct >= 50:
            out.append(Achievement(GOAL_MILESTONE, MEDIUM, f"Reached {pct}% of your {name} goal", when))

    return out
