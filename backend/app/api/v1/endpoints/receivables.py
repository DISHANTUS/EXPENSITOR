"""Receivables CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import ReceivableSourceType, ReceivableStatus
from app.schemas.common import Page
from app.schemas.receivable import ReceivableCreate, ReceivableRead, ReceivableUpdate
from app.services import receivables_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/receivables", tags=["receivables"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receivable not found")


def _to_422(exc: Exception) -> HTTPException:
    if isinstance(exc, CurrencyNotFoundError):
        detail = f"Unsupported currency: {exc.code}"
    elif isinstance(exc, InvalidOperationError):
        detail = exc.message
    else:
        detail = str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=ReceivableRead, status_code=status.HTTP_201_CREATED)
async def create_receivable(data: ReceivableCreate, current_user: CurrentUser, db: DbSession) -> ReceivableRead:
    try:
        return await receivables_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc


@router.get("", response_model=Page[ReceivableRead])
async def list_receivables(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: ReceivableStatus | None = Query(default=None, alias="status"),
    source_type: ReceivableSourceType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[ReceivableRead]:
    items, total = await receivables_service.list_(
        db, current_user.id, status=status_filter, source_type=source_type, limit=limit, offset=offset
    )
    return Page[ReceivableRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/{receivable_id}", response_model=ReceivableRead)
async def get_receivable(receivable_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ReceivableRead:
    try:
        return await receivables_service.get(db, current_user.id, receivable_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.patch("/{receivable_id}", response_model=ReceivableRead)
async def update_receivable(
    receivable_id: uuid.UUID, data: ReceivableUpdate, current_user: CurrentUser, db: DbSession
) -> ReceivableRead:
    try:
        return await receivables_service.update(db, current_user.id, receivable_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc


@router.delete("/{receivable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_receivable(receivable_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await receivables_service.soft_delete(db, current_user.id, receivable_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
