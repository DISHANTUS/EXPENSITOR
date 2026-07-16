"""End-of-day report endpoint (derived on read; nothing stored, nothing scheduled)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.daily_report import DailyReportOut
from app.services import daily_report_service

router = APIRouter(prefix="/daily-report", tags=["daily-report"])


@router.get("", response_model=DailyReportOut, summary="How today went")
async def get_daily_report(
    db: DbSession,
    current_user: CurrentUser,
    hour: int | None = Query(default=None, ge=0, le=23),
) -> DailyReportOut:
    # `hour` is the device's local hour, same convention as the greeting: the
    # server's clock can't tell whether THIS user's day is over, and calling a
    # day "saved" while they're still out for dinner is the failure to avoid.
    result = await daily_report_service.report(db, current_user.id, hour=hour)
    return DailyReportOut(**result)
