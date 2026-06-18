"""Importance gating + follow-up cadence (Sprint 4b-5a, pure/deterministic).

Decides whether a piece of advice is worth following up — and how often. The
companion should ask aggressively about what matters (goals, money lent out,
the monthly budget) and never nag about a single coffee.

  HIGH    → ask after 14 days, then keep re-asking (repeat) until answered
  MEDIUM  → ask once after 30 days
  LOW     → never follow up

No follow-up window  ==>  follow_up_due is None (the loop simply never asks).
"""

from __future__ import annotations

from datetime import date, timedelta

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

# Classified primarily by what the advice is ABOUT (subject_type), kind as a hint.
_HIGH_SUBJECTS = {"goal", "savings_goal", "loan_repayment", "monthly_budget", "budget", "person"}
_MEDIUM_SUBJECTS = {"category", "subscription", "travel", "food_reduction"}
_LOW_SUBJECTS = {"single_expense", "one_day_overspend", "expense"}

# Cadence: (days until first ask, keep re-asking?)
_CADENCE: dict[str, tuple[int | None, bool]] = {
    HIGH: (14, True),
    MEDIUM: (30, False),
    LOW: (None, False),
}
# How long after the due date we keep re-asking a HIGH item before giving up.
REPEAT_INTERVAL_DAYS = 14
EXPIRE_AFTER_DAYS = 120


def importance_for(kind: str, subject_type: str) -> str:
    st = (subject_type or "").lower()
    if st in _LOW_SUBJECTS:
        return LOW
    if st in _HIGH_SUBJECTS:
        return HIGH
    if st in _MEDIUM_SUBJECTS:
        return MEDIUM
    # Fall back on the kind when the subject is unfamiliar.
    if kind in ("forecast", "relationship", "budget"):
        return HIGH
    if kind == "recommendation":
        return MEDIUM
    return MEDIUM


def cadence_for(importance: str) -> tuple[int | None, bool]:
    return _CADENCE.get(importance, (30, False))


def first_due(today: date, importance: str) -> date | None:
    days, _ = cadence_for(importance)
    return None if days is None else today + timedelta(days=days)


def next_due(today: date, importance: str) -> date | None:
    """When to re-ask a HIGH item that was due but went unanswered (None = stop)."""
    _, repeat = cadence_for(importance)
    return today + timedelta(days=REPEAT_INTERVAL_DAYS) if repeat else None
