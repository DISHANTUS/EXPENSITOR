"""Outcome endpoints (Phase E): record / list / effectiveness."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.outcome import OutcomeReportIn
from app.services import outcome_service

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def report_outcome(data: OutcomeReportIn, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    try:
        data.validate_enums()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    row = await outcome_service.record(db, current_user.id, data)
    return {"id": str(row.id), "kind": row.kind, "outcome": row.outcome, "circumstance": row.circumstance}


@router.get("")
async def list_outcomes(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    return {"items": await outcome_service.list_outcomes(db, current_user.id)}


@router.get("/effectiveness")
async def effectiveness(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    return {"levers": await outcome_service.effectiveness(db, current_user.id)}
