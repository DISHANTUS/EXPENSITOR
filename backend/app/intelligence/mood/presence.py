"""Companion presence score (Sprint 4c-A, pure + INTERNAL).

How much do we know about this user? Drives greeting depth / lesson use / memory
references / Future-Me quality later. Not shown in the UI yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Presence:
    score: int       # 0..100
    band: str        # new | learning | familiar | deeply_personalized


def compute(*, days_logged: int, has_goal: bool, has_income: bool, has_receivables: bool,
            lessons: int, advice_count: int) -> Presence:
    score = 0.0
    score += min(days_logged, 30) / 30 * 35      # breadth of activity
    score += 15 if has_goal else 0
    score += 10 if has_income else 0
    score += 10 if has_receivables else 0
    score += min(lessons, 3) / 3 * 15            # taught lessons
    score += min(advice_count, 5) / 5 * 15       # tracked advice / engagement
    s = int(round(min(100.0, score)))
    if s < 20:
        band = "new"
    elif s < 50:
        band = "learning"
    elif s < 80:
        band = "familiar"
    else:
        band = "deeply_personalized"
    return Presence(score=s, band=band)
