"""Home "thought" schema (UI-X)."""

from __future__ import annotations

from pydantic import BaseModel


class HomeThought(BaseModel):
    lines: list[str]
    mood: str   # idle | celebrating | concerned (drives the orb)
