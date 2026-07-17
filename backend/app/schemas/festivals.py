"""Festival schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FestivalUpcoming(BaseModel):
    name: str
    date: str
    days_away: int
    approximate: bool = False      # moon-sighting festivals can shift by a day
    last_time: dict[str, Any] | None = None   # measured from the user's own ledger, or null
    line: str


class FestivalsOut(BaseModel):
    """`ready` is false only when the baked calendar has run out of years — in
    which case we say nothing rather than guess a lunar date."""

    ready: bool
    reason: str | None = None
    currency: str | None = None
    calendar_until: str
    upcoming: list[FestivalUpcoming] = []
