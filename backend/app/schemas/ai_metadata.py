"""Standardized advisor metadata, stored as JSONB across entities.

A common shape so future systems (habit profiling, life chapters, forecasting,
memory recap) read the same keys everywhere. ``extra="allow"`` keeps it
forward-compatible — new keys can be added without a migration.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AiMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    why: str | None = None              # the user's reason ("what/why/afterward" — why)
    confidence: float = 1.0             # how sure the advisor is (0..1)
    importance: str | None = None       # mirrors the entity's importance column
    chapter: str | None = None          # life chapter, e.g. "Japan Preparation"
    advisor_notes: list[str] = Field(default_factory=list)
    memory_tags: list[str] = Field(default_factory=list)


def default_ai_metadata(*, why: str | None = None, importance: str = "medium") -> dict[str, Any]:
    return AiMetadata(why=why, importance=importance).model_dump()
