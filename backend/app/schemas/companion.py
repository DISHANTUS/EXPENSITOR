"""Companion request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CompanionCategory,
    CompanionEntityType,
    CompanionEventType,
    CompanionSeverity,
)


class CompanionEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: CompanionEventType
    surface: str | None = Field(default=None, max_length=100)
    action: str | None = Field(default=None, max_length=100)
    entity_type: CompanionEntityType | None = None
    entity_id: uuid.UUID | None = None
    payload: dict[str, Any] | None = None


class CompanionMessageOut(BaseModel):
    kind: str                      # "help" | "insight"
    category: CompanionCategory
    type: str
    surface: str | None = None
    severity: CompanionSeverity
    title: str
    message: str
    facts: dict[str, Any] = Field(default_factory=dict)
    insight_id: uuid.UUID | None = None


class CompanionEventResponse(BaseModel):
    event_id: uuid.UUID
    messages: list[CompanionMessageOut]


class CompanionInsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: CompanionCategory
    type: str
    surface: str | None
    severity: CompanionSeverity
    title: str
    message: str
    facts: dict[str, Any]
    source: str
    related_entity_type: CompanionEntityType | None
    related_entity_id: uuid.UUID | None
    is_read: bool
    created_at: datetime


class UnreadCountOut(BaseModel):
    count: int
