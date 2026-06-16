"""Savings-goal endpoints (Tier 1): CRUD, derived state, user-driven recovery."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import SavingsGoalStatus
from app.schemas.common import Page
from app.schemas.savings import RecoveryIn, SavingsGoalCreate, SavingsGoalRead, SavingsGoalUpdate
from app.services import savings_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/savings-goals", tags=["savings-goals"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Savings goal not found")


def _to_422(exc: Exception) -> HTTPException:
    detail = f"Unsupported currency: {exc.code}" if isinstance(exc, CurrencyNotFoundError) else str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=SavingsGoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(data: SavingsGoalCreate, current_user: CurrentUser, db: DbSession) -> SavingsGoalRead:
    try:
        row = await savings_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _to_422(exc) from exc
    return SavingsGoalRead.model_validate(row)


@router.get("", response_model=Page[SavingsGoalRead])
async def list_goals(
    current_user: CurrentUser, db: DbSession,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    status_filter: SavingsGoalStatus | None = Query(default=None, alias="status"),
) -> Page[SavingsGoalRead]:
    rows, total = await savings_service.list_(db, current_user.id, limit=limit, offset=offset, status=status_filter)
    return Page[SavingsGoalRead](
        items=[SavingsGoalRead.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{goal_id}", response_model=SavingsGoalRead)
async def get_goal(goal_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> SavingsGoalRead:
    try:
        row = await savings_service.get(db, current_user.id, goal_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return SavingsGoalRead.model_validate(row)


@router.get("/{goal_id}/state")
async def get_goal_state(goal_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Derived progress/status + why-at-risk reasons + recovery options + advisor explanation."""
    try:
        return await savings_service.get_state(db, current_user.id, goal_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.patch("/{goal_id}", response_model=SavingsGoalRead)
async def update_goal(goal_id: uuid.UUID, data: SavingsGoalUpdate, current_user: CurrentUser, db: DbSession) -> SavingsGoalRead:
    try:
        row = await savings_service.update(db, current_user.id, goal_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _to_422(exc) from exc
    return SavingsGoalRead.model_validate(row)


@router.post("/{goal_id}/recovery", response_model=SavingsGoalRead)
async def apply_recovery(goal_id: uuid.UUID, data: RecoveryIn, current_user: CurrentUser, db: DbSession) -> SavingsGoalRead:
    """Apply the user's explicit recovery choice. The system never decides this."""
    try:
        row = await savings_service.apply_recovery(db, current_user.id, goal_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (InvalidOperationError, CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _to_422(exc) from exc
    return SavingsGoalRead.model_validate(row)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await savings_service.soft_delete(db, current_user.id, goal_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
