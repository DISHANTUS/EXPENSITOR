"""Daily-plan (per-day budget) schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class DailyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_date: date
    planned_budget: Decimal | None
    locked_at: datetime | None
    modified_after_start: bool
    overspend_reason: str | None
    created_at: datetime
    updated_at: datetime


class DailyPlanUpsert(BaseModel):
    """Set/adjust a day's budget and/or record an overspend reason.

    ``override`` must be true to change the budget after spending has begun for
    today (the start-of-day lock); the change is then flagged for analysis.
    """

    model_config = ConfigDict(extra="forbid")

    planned_budget: Money | None = None
    overspend_reason: str | None = Field(default=None, max_length=2000)
    override: bool = False
