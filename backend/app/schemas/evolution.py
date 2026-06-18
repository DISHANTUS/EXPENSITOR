"""Companion Evolution / Reflection schemas (Sprint 8).

Advary reflecting on the user's journey — deterministic observations composed
from data that already exists. Meaningful, never fake emotion.
"""

from __future__ import annotations

from pydantic import BaseModel


class ReflectionLine(BaseModel):
    icon: str
    text: str


class ChapterProgress(BaseModel):
    label: str
    subtitle: str = ""
    started: str | None = None     # ISO date of the chapter's first moment
    progress: int | None = None    # 0–100, how far through this chapter (past vs ahead)
    moments: int = 0               # entries recorded in this chapter


class Milestone(BaseModel):
    icon: str
    label: str
    date: str | None = None        # ISO date
    tense: str = "past"            # past | future


class EvolutionView(BaseModel):
    days_with_advary: int
    reflections: list[ReflectionLine]
    current_chapter: ChapterProgress | None = None
    longest_chapter: str | None = None
    milestones: list[Milestone]


class MonthlyReflection(BaseModel):
    month_label: str               # "June 2026"
    available: bool                # false when there's too little activity to reflect
    headline: str
    within_budget_days: int = 0
    tracked_days: int = 0
    biggest_win: str | None = None
    most_active_relationship: str | None = None
    most_improved_area: str | None = None
