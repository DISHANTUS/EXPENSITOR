"""Life-event schemas (Sprint 6b) — user-entered timeline milestones."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LifeEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    event_date: date
    kind: str = Field(default="milestone", max_length=30)
    icon: str | None = Field(default=None, max_length=8)
    note: str | None = Field(default=None, max_length=500)


class LifeEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    event_date: date
    kind: str
    icon: str | None
    note: str | None
    created_at: datetime
