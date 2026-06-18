"""Life Timeline schemas (Sprint 6a)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

_Date = date  # alias so the field literally named `date` doesn't shadow the type


class TimelineEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: _Date | None = None
    title: str
    detail: str = ""
    kind: str                  # achievement | goal | loan | event | lesson | income | life_event | forecast
    importance: str            # life_milestone | high | medium | low
    when: str                  # past | present | future
    icon: str = "•"
    person: str | None = None  # who this involves (7)


class TimelineChapter(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str                 # chapter title (e.g. "Japan Preparation")
    subtitle: str = ""
    entries: list[TimelineEntry]


class Timeline(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chapters: list[TimelineChapter]
    past_count: int
    present_count: int
    future_count: int
    headline: str


class TimelineSearchResult(BaseModel):
    summary: str               # spoken/printed one-liner ("3 things involving Ravi")
    entries: list[TimelineEntry] = []
