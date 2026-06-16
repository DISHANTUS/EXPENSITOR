"""Planned-expense CRUD endpoints (paginated, filterable)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import PlannedExpensePriority, PlannedExpenseStatus
from app.schemas.common import Page
from app.schemas.planned_expense import (
    PlannedExpenseCreate,
    PlannedExpenseRead,
    PlannedExpenseUpdate,
)
from app.services import planned_expense_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    FieldNotNullableError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/planned-expenses", tags=["planned-expenses"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Planned expense not found"
)


def _to_422(exc: Exception) -> HTTPException:
    if isinstance(exc, CurrencyNotFoundError):
        detail = f"Unsupported currency: {exc.code}"
    elif isinstance(exc, FieldNotNullableError):
        detail = f"Field '{exc.field}' cannot be null"
    elif isinstance(exc, InvalidOperationError):
        detail = exc.message
    else:
        detail = str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=PlannedExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_planned_expense(
    data: PlannedExpenseCreate, current_user: CurrentUser, db: DbSession
) -> PlannedExpenseRead:
    try:
        row = await planned_expense_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc
    return PlannedExpenseRead.model_validate(row)


@router.get("", response_model=Page[PlannedExpenseRead])
async def list_planned_expenses(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: PlannedExpenseStatus | None = Query(default=None),
    priority: PlannedExpensePriority | None = Query(default=None),
) -> Page[PlannedExpenseRead]:
    rows, total = await planned_expense_service.list_(
        db, current_user.id, limit=limit, offset=offset, status=status, priority=priority
    )
    return Page[PlannedExpenseRead](
        items=[PlannedExpenseRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{planned_id}", response_model=PlannedExpenseRead)
async def get_planned_expense(
    planned_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> PlannedExpenseRead:
    try:
        row = await planned_expense_service.get(db, current_user.id, planned_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return PlannedExpenseRead.model_validate(row)


@router.patch("/{planned_id}", response_model=PlannedExpenseRead)
async def update_planned_expense(
    planned_id: uuid.UUID,
    data: PlannedExpenseUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> PlannedExpenseRead:
    try:
        row = await planned_expense_service.update(db, current_user.id, planned_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError, FieldNotNullableError) as exc:
        raise _to_422(exc) from exc
    return PlannedExpenseRead.model_validate(row)


@router.delete("/{planned_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planned_expense(
    planned_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Response:
    try:
        await planned_expense_service.soft_delete(db, current_user.id, planned_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
