"""Actual-income CRUD endpoints (paginated)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import IncomeSourceType
from app.schemas.common import Page
from app.schemas.income import IncomeCreate, IncomeRead, IncomeUpdate
from app.services import income_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/incomes", tags=["incomes"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income not found")


def _currency_error(exc: CurrencyNotFoundError | RateNotAvailableError) -> HTTPException:
    detail = f"Unsupported currency: {exc.code}" if isinstance(exc, CurrencyNotFoundError) else str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=IncomeRead, status_code=status.HTTP_201_CREATED)
async def create_income(data: IncomeCreate, current_user: CurrentUser, db: DbSession) -> IncomeRead:
    try:
        row = await income_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _currency_error(exc) from exc
    return IncomeRead.model_validate(row)


@router.get("", response_model=Page[IncomeRead])
async def list_incomes(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source_type: IncomeSourceType | None = Query(default=None),
) -> Page[IncomeRead]:
    rows, total = await income_service.list_(
        db, current_user.id, limit=limit, offset=offset, source_type=source_type
    )
    return Page[IncomeRead](
        items=[IncomeRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{income_id}", response_model=IncomeRead)
async def get_income(income_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> IncomeRead:
    try:
        row = await income_service.get(db, current_user.id, income_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return IncomeRead.model_validate(row)


@router.patch("/{income_id}", response_model=IncomeRead)
async def update_income(
    income_id: uuid.UUID, data: IncomeUpdate, current_user: CurrentUser, db: DbSession
) -> IncomeRead:
    try:
        row = await income_service.update(db, current_user.id, income_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _currency_error(exc) from exc
    return IncomeRead.model_validate(row)


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(income_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await income_service.soft_delete(db, current_user.id, income_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
