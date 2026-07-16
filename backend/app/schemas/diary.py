"""Diary schemas."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiaryEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    entry_date: date | None = None  # defaults to the user's today


class DiaryAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=500)


class DiaryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entry_date: date
    text: str
    details: list[dict[str, Any]] = []
    closed: bool = False


class DiaryEntryWithQuestion(BaseModel):
    """An entry plus the next thing Advary would like to ask about it. A null
    question is normal — it means there's nothing worth asking, not an error."""

    entry: DiaryEntryOut
    question: str | None = None


class PatternObservation(BaseModel):
    kind: str      # mention | weekday | first_week
    word: str
    text: str


class PatternAsk(BaseModel):
    word: str
    question: str


class DiaryPatternsOut(BaseModel):
    """What the diary adds up to. `ready` is false until there's enough to say
    anything — under the threshold this stays deliberately empty rather than
    guessing."""

    ready: bool
    entries: int
    days: int = 0
    needed: int = 0
    observations: list[PatternObservation] = []
    ask: PatternAsk | None = None
