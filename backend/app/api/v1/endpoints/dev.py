"""Developer-only tools (gated by is_developer / allow-list)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DbSession, RequireDeveloper
from app.services import reset_service

router = APIRouter(prefix="/dev", tags=["dev"])


class CalendarPreviewOut(BaseModel):
    created: int
    message: str


@router.post("/calendar-preview", response_model=CalendarPreviewOut,
             summary="Seed this month with one of each event type to test calendar animations (developer-only)")
async def calendar_preview(current_user: RequireDeveloper, db: DbSession) -> CalendarPreviewOut:
    n = await reset_service.seed_calendar_preview(db, current_user.id)
    return CalendarPreviewOut(created=n, message=f"Added {n} sample events this month — open the calendar.")
