"""Future Me schemas (Sprint 6b) — the forward half of the life story."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

_Date = date  # alias so a field named `date` doesn't shadow the type


class FutureMePath(BaseModel):
    mode: str                # current | optimistic | conservative
    label: str
    eta: _Date | None = None
    monthly_rate: Decimal
    narrative: str


class FutureMeLever(BaseModel):
    label: str
    ref: str                 # round-trips to /advisor/forecast


class FutureMeMilestone(BaseModel):
    date: _Date | None = None
    title: str
    detail: str = ""
    kind: str                # goal | loan | event | life_event | forecast
    icon: str = "•"


class FutureMeView(BaseModel):
    headline: str
    confidence: str
    reasoning: str = ""
    currency: str
    paths: list[FutureMePath] = []
    levers: list[FutureMeLever] = []
    milestones: list[FutureMeMilestone] = []
