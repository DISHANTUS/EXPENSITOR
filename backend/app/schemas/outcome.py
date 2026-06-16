"""Schemas for user-reported outcomes (Phase E)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

_KINDS = {"decision", "recommendation", "goal", "plan"}
_STATUSES = {"success", "partial", "failed", "abandoned", "ahead", "on_track", "behind", "missed", "unknown"}


class OutcomeReportIn(BaseModel):
    kind: str = Field(description="decision | recommendation | goal | plan")
    subject_type: str
    outcome: str = Field(description="success | partial | failed | abandoned | ahead | on_track | behind | missed | unknown")
    subject_id: uuid.UUID | None = None
    lever_key: str | None = None
    category_id: uuid.UUID | None = None
    outcome_reason: str | None = None
    expected_value: Decimal | None = None
    actual_value: Decimal | None = None

    def validate_enums(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(f"invalid kind: {self.kind}")
        if self.outcome not in _STATUSES:
            raise ValueError(f"invalid outcome: {self.outcome}")
