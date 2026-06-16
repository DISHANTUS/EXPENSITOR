"""Category response schema (read-only list for the expense picker)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    icon: str | None
    color: str | None
    is_system: bool
    is_essential: bool
