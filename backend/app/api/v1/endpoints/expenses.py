"""Expense CRUD endpoints (paginated, filterable)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.services import expense_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    FieldNotNullableError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")


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


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(data: ExpenseCreate, current_user: CurrentUser, db: DbSession) -> ExpenseRead:
    try:
        row = await expense_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc
    return ExpenseRead.model_validate(row)


@router.get("", response_model=Page[ExpenseRead])
async def list_expenses(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> Page[ExpenseRead]:
    rows, total = await expense_service.list_(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
    )
    return Page[ExpenseRead](
        items=[ExpenseRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{expense_id}", response_model=ExpenseRead)
async def get_expense(expense_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ExpenseRead:
    try:
        row = await expense_service.get(db, current_user.id, expense_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return ExpenseRead.model_validate(row)


@router.patch("/{expense_id}", response_model=ExpenseRead)
async def update_expense(
    expense_id: uuid.UUID, data: ExpenseUpdate, current_user: CurrentUser, db: DbSession
) -> ExpenseRead:
    try:
        row = await expense_service.update(db, current_user.id, expense_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError, FieldNotNullableError) as exc:
        raise _to_422(exc) from exc
    return ExpenseRead.model_validate(row)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await expense_service.soft_delete(db, current_user.id, expense_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
