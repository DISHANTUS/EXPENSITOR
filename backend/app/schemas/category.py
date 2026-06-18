"""Category response schema (read-only list for the expense picker)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    """Create a user-owned category (the 'Other → specify' custom value)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=9)
    is_essential: bool = False


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str | None
    color: str | None
    is_system: bool
    is_essential: bool
