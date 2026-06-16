"""Income-source CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import IncomeKind, IncomeSourceType
from app.schemas.income_source import IncomeSourceCreate, IncomeSourceRead, IncomeSourceUpdate
from app.services import income_source_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/income-sources", tags=["income-sources"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income source not found")


def _currency_error(exc: CurrencyNotFoundError | RateNotAvailableError) -> HTTPException:
    detail = f"Unsupported currency: {exc.code}" if isinstance(exc, CurrencyNotFoundError) else str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=IncomeSourceRead, status_code=status.HTTP_201_CREATED)
async def create_income_source(
    data: IncomeSourceCreate, current_user: CurrentUser, db: DbSession
) -> IncomeSourceRead:
    try:
        row = await income_source_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _currency_error(exc) from exc
    return IncomeSourceRead.model_validate(row)


@router.get("", response_model=list[IncomeSourceRead])
async def list_income_sources(
    current_user: CurrentUser,
    db: DbSession,
    is_active: bool | None = Query(default=None),
    source_type: IncomeSourceType | None = Query(default=None),
    kind: IncomeKind | None = Query(default=None),
) -> list[IncomeSourceRead]:
    rows = await income_source_service.list_(
        db, current_user.id, is_active=is_active, source_type=source_type, kind=kind
    )
    return [IncomeSourceRead.model_validate(row) for row in rows]


@router.get("/{source_id}", response_model=IncomeSourceRead)
async def get_income_source(
    source_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> IncomeSourceRead:
    try:
        row = await income_source_service.get(db, current_user.id, source_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return IncomeSourceRead.model_validate(row)


@router.patch("/{source_id}", response_model=IncomeSourceRead)
async def update_income_source(
    source_id: uuid.UUID, data: IncomeSourceUpdate, current_user: CurrentUser, db: DbSession
) -> IncomeSourceRead:
    try:
        row = await income_source_service.update(db, current_user.id, source_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _currency_error(exc) from exc
    except InvalidOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc
    return IncomeSourceRead.model_validate(row)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income_source(
    source_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Response:
    try:
        await income_source_service.soft_delete(db, current_user.id, source_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
