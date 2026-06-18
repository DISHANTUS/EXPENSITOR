"""First-launch guided tour schemas."""

from __future__ import annotations

from pydantic import BaseModel


class TourStepOut(BaseModel):
    key: str
    route: str
    icon: str
    title: str
    narration: str
    spoken_text: str


class TourOut(BaseModel):
    companion_name: str
    steps: list[TourStepOut]


class TourCompleteOut(BaseModel):
    ok: bool = True
    has_seen_tour: bool = True
