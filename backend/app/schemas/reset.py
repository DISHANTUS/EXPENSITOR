"""Reset / Clean-Slate schemas (pre-Sprint-8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["soft", "full", "demo"]


class ResetOut(BaseModel):
    ok: bool = True
    mode: str
    message: str
