"""Calendar endpoints: month grid, single-day detail, marker registry."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.calendar import DayDetail, MarkerTypeOut, MonthView
from app.services import calendar_service
from app.services.marker_types import all_markers

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/marker-types", response_model=list[MarkerTypeOut], summary="Marker registry")
async def marker_types() -> list[MarkerTypeOut]:
    return [MarkerTypeOut(**m.__dict__) for m in all_markers()]


@router.get("/month", response_model=MonthView, summary="Month grid with per-day markers")
async def month(
    current_user: CurrentUser,
    db: DbSession,
    year: int = Query(ge=1970, le=2100),
    month: int = Query(ge=1, le=12),
) -> MonthView:
    today = await calendar_service.user_today(db, current_user.id)
    return await calendar_service.month_view(db, current_user.id, year, month, today=today)


@router.get("/day/{day}", response_model=DayDetail, summary="Single-day detail")
async def day(day: date, current_user: CurrentUser, db: DbSession) -> DayDetail:
    today = await calendar_service.user_today(db, current_user.id)
    return await calendar_service.day_detail(db, current_user.id, day, today=today)
