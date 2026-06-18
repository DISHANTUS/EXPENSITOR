"""Reason-interpretation schemas (Other -> specify / natural-language reasons)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReasonInterpretIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class ReasonInterpretOut(BaseModel):
    original: str       # the user's exact words (source of truth)
    label: str          # AI's short interpretation (an interpretation layer only)
    tags: list[str]
    confidence: float
    needs_more: bool    # true -> the UI should gently ask for a bit more detail
