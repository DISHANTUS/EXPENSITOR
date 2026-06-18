"""Home Memory Strip stats (UI-X)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class HomeStats(BaseModel):
    days_with_advary: int
    goals_completed: int
    goals_active: int
    relationship_count: int
    total_saved: Decimal
    currency: str
    strongest_habit: str | None = None
    biggest_win: str | None = None
