"""Schemas for preference memory / adaptive planning (C7b)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecommendationAction, RejectionReason


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1, max_length=120)
    action: RecommendationAction
    reason: RejectionReason | None = None
    reason_context: str | None = Field(default=None, max_length=500)   # D11 (explanations only)
    emotional_importance: str | None = Field(default=None, max_length=20)  # D12 (low|medium|high|critical)
    note: str | None = Field(default=None, max_length=500)


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excluded_levers: list[str] | None = None
    preferred_levers: list[str] | None = None
    flags: dict[str, Any] | None = None


class PolicyOut(BaseModel):
    policy: dict[str, Any]
