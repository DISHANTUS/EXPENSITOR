"""Budget derivation endpoints (Budget Setup output)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.budget import BudgetSummary
from app.services import budget_service

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/summary", response_model=BudgetSummary, summary="Derived monthly/weekly/daily budget")
async def budget_summary(current_user: CurrentUser, db: DbSession) -> BudgetSummary:
    return await budget_service.summary(db, current_user.id)


@router.post("/apply", response_model=BudgetSummary, summary="Apply derived budget (sets monthly threshold)")
async def apply_budget(current_user: CurrentUser, db: DbSession) -> BudgetSummary:
    return await budget_service.apply(db, current_user.id)
