"""Schema for the Natural-Language Action Layer endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    confirm: bool = False
    answers: dict[str, Any] | None = None     # fills clarifications / carries modifier inputs
    request_id: str | None = Field(default=None, max_length=80)  # idempotency for confirmed actions
