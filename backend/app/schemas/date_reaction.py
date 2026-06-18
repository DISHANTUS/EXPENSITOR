"""Date → Orb reaction schema (UI-X — the calendar as memory)."""

from __future__ import annotations

from pydantic import BaseModel


class DateReaction(BaseModel):
    line: str               # what Advary says about that day
    mood: str               # idle | celebrating | concerned (drives the orb)
    emoji: str              # the day's dominant marker glyph
