"""Per-day budget endpoints: read + upsert (with start-of-day lock)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.daily_plan import DailyPlanRead, DailyPlanUpsert
from app.services import calendar_service, daily_plan_service
from app.services.exceptions import InvalidOperationError

router = APIRouter(prefix="/daily-plans", tags=["daily-plans"])


@router.get("/{day}", response_model=DailyPlanRead | None, summary="Get a day's budget plan")
async def get_daily_plan(day: date, current_user: CurrentUser, db: DbSession) -> DailyPlanRead | None:
    row = await daily_plan_service.get(db, current_user.id, day)
    return DailyPlanRead.model_validate(row) if row is not None else None


@router.put("/{day}", response_model=DailyPlanRead, summary="Set/adjust budget or overspend reason")
async def upsert_daily_plan(
    day: date, data: DailyPlanUpsert, current_user: CurrentUser, db: DbSession
) -> DailyPlanRead:
    today = await calendar_service.user_today(db, current_user.id)
    try:
        row = await daily_plan_service.upsert(db, current_user.id, day, data, today=today)
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    return DailyPlanRead.model_validate(row)
