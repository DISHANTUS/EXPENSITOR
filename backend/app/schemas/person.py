"""Person (relationship memory) schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RelationshipType

Reliability = Annotated[Decimal, Field(ge=0, le=1, max_digits=4, decimal_places=3)]


class PersonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    relationship_type: RelationshipType
    nickname: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    reliability_score: Reliability | None = None
    tags: list[str] | None = None
    ai_metadata: dict[str, Any] | None = None


class PersonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    relationship_type: RelationshipType | None = None
    nickname: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    reliability_score: Reliability | None = None
    tags: list[str] | None = None
    ai_metadata: dict[str, Any] | None = None


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    nickname: str | None
    relationship_type: RelationshipType
    notes: str | None
    reliability_score: Decimal | None
    first_interaction_at: datetime | None
    last_interaction_at: datetime | None
    tags: list[Any] | None
    ai_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
