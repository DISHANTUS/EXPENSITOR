"""Mood library (Sprint 4c-A, pure/deterministic).

The companion's emotional vocabulary. Every mood has a priority and a lifetime so
the rotation engine can order and expire them. Emojis align with the calendar
`marker_types` vocabulary.

WEATHER-PROOFING (hard rule): the worst mood is 😟 *concerned*. There is no
angry/sad/dead mood — the companion is an advisor, never a disappointed parent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import IntEnum


class Priority(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


# lifetime keys -> how many days a mood stays "active" from its trigger date.
# (sub-day windows degrade to same-day in 4c-A; intraday timing arrives with 4c-B.)
_LIFETIME_DAYS = {
    "hours_1": 0, "end_of_day": 0, "until_midnight": 0, "today": 0,
    "days_3": 3, "days_7": 7, "persistent": 0,
}


@dataclass(frozen=True)
class Mood:
    id: str
    emoji: str
    label: str
    kind: str          # base | event | relationship | achievement | seasonal | override
    priority: Priority
    lifetime: str      # key in _LIFETIME_DAYS


def _m(id, emoji, label, kind, priority, lifetime="today"):
    return Mood(id, emoji, label, kind, priority, lifetime)


_DEFS = [
    # --- base moods (resting face; never worse than concerned) ---
    _m("big_win", "🥳", "Thrilled", "base", Priority.HIGH, "persistent"),
    _m("saving_well", "😄", "Pleased", "base", Priority.LOW, "persistent"),
    _m("goal_progress", "😎", "On track", "base", Priority.LOW, "persistent"),
    _m("on_budget", "😊", "Content", "base", Priority.LOW, "persistent"),
    _m("neutral", "🙂", "Steady", "base", Priority.LOW, "persistent"),
    _m("slightly_over", "😕", "A little watchful", "base", Priority.LOW, "persistent"),
    _m("concerned", "😟", "Concerned", "base", Priority.MEDIUM, "persistent"),  # WORST allowed

    # --- emergency overrides (CRITICAL: dominate the session) ---
    _m("goal_completed", "🏆", "Goal completed!", "override", Priority.CRITICAL, "days_3"),
    _m("first_salary", "🎉", "First income!", "override", Priority.CRITICAL, "days_7"),
    _m("debt_cleared", "🎉", "Debt cleared!", "override", Priority.CRITICAL, "days_3"),
    _m("birthday", "🎂", "Happy birthday!", "override", Priority.CRITICAL, "until_midnight"),
    _m("anniversary", "💞", "Anniversary", "override", Priority.CRITICAL, "until_midnight"),
    _m("graduation", "🎓", "Graduation!", "override", Priority.CRITICAL, "days_3"),
    _m("job_offer", "💼", "Job offer!", "override", Priority.CRITICAL, "days_3"),

    # --- event moods ---
    _m("salary", "💰", "Salary arrived", "event", Priority.LOW, "end_of_day"),
    _m("returned", "💰", "Money returned", "event", Priority.LOW, "end_of_day"),
    _m("gift", "🎁", "A gift", "event", Priority.LOW, "hours_1"),
    _m("lent", "💸", "Lent money", "event", Priority.LOW, "hours_1"),
    _m("date", "❤️", "A date", "event", Priority.MEDIUM, "until_midnight"),
    _m("trip", "✈️", "A trip", "event", Priority.MEDIUM, "until_midnight"),
    _m("exam", "📝", "Exam day", "event", Priority.MEDIUM, "today"),
    _m("interview", "💼", "Interview", "event", Priority.MEDIUM, "today"),
    _m("certification", "🎓", "Certification", "event", Priority.HIGH, "today"),
    _m("jlpt", "🇯🇵", "JLPT", "event", Priority.HIGH, "today"),

    # --- relationship moods ---
    _m("family_support", "👨‍👩‍👦", "Family support", "relationship", Priority.LOW, "end_of_day"),
    _m("mother_gift", "👩", "From your mother", "relationship", Priority.LOW, "end_of_day"),
    _m("father_gift", "👨", "From your father", "relationship", Priority.LOW, "end_of_day"),

    # --- achievement badges (a LAYER over the base, not the resting face) ---
    _m("streak", "🔥", "Budget streak", "achievement", Priority.MEDIUM, "today"),
    _m("perfect_week", "⭐", "Perfect week", "achievement", Priority.MEDIUM, "days_3"),
    _m("goal_progress_badge", "👑", "Goal progress", "achievement", Priority.HIGH, "days_3"),
    _m("milestone", "💎", "Milestone", "achievement", Priority.HIGH, "days_3"),

    # --- seasonal (registry only in 4c-A; detection logic lands later) ---
    _m("christmas", "🎄", "Christmas", "seasonal", Priority.MEDIUM, "until_midnight"),
    _m("diwali", "🪔", "Diwali", "seasonal", Priority.MEDIUM, "until_midnight"),
    _m("new_year", "🎆", "New Year", "seasonal", Priority.MEDIUM, "until_midnight"),
]

MOODS: dict[str, Mood] = {m.id: m for m in _DEFS}

# The single worst base mood the engine may ever show.
WORST_BASE = "concerned"
_BASE_RANK = ["concerned", "slightly_over", "neutral", "on_budget", "goal_progress", "saving_well", "big_win"]


def get(mood_id: str) -> Mood:
    return MOODS[mood_id]


def lifetime_days(lifetime: str) -> int:
    return _LIFETIME_DAYS.get(lifetime, 0)


def display_until(lifetime: str, trigger_day: date) -> date:
    return trigger_day + timedelta(days=lifetime_days(lifetime))


def is_active(mood: Mood, trigger_day: date, today: date) -> bool:
    """A mood is active from its trigger day through its lifetime window."""
    return trigger_day <= today <= display_until(mood.lifetime, trigger_day)


def weather_proof(mood_id: str) -> str:
    """Defensive clamp — never return a mood worse than 'concerned'."""
    if mood_id in _BASE_RANK:
        return mood_id
    return mood_id  # non-base moods are all neutral/positive by construction


# Calendar marker key -> mood id (today's markers become event moods).
MARKER_TO_MOOD = {
    "lent": "lent", "returned": "returned",
    "income": "salary", "income_salary": "salary", "income_gift": "gift",
    "income_family": "family_support", "income_bonus": "salary", "income_freelance": "salary",
    "gift": "gift", "surprise_gift": "gift",
    "trip": "trip", "outing": "date", "anniversary": "anniversary", "birthday": "birthday",
    "graduation": "graduation", "celebration": "birthday", "festival": "diwali",
    "goal_completed": "goal_completed", "goal_milestone": "milestone",
}
