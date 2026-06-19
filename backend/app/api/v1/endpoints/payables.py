"""Payables CRUD endpoints — money the user borrowed and owes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import PayableStatus
from app.schemas.common import Page
from app.schemas.payable import PayableCreate, PayableRead, PayableUpdate
from app.services import payable_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/payables", tags=["payables"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payable not found")


def _to_422(exc: Exception) -> HTTPException:
    if isinstance(exc, CurrencyNotFoundError):
        detail = f"Unsupported currency: {exc.code}"
    elif isinstance(exc, InvalidOperationError):
        detail = exc.message
    else:
        detail = str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=PayableRead, status_code=status.HTTP_201_CREATED)
async def create_payable(data: PayableCreate, current_user: CurrentUser, db: DbSession) -> PayableRead:
    try:
        return await payable_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc


@router.get("", response_model=Page[PayableRead])
async def list_payables(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: PayableStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[PayableRead]:
    items, total = await payable_service.list_(
        db, current_user.id, status=status_filter, limit=limit, offset=offset
    )
    return Page[PayableRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/{payable_id}", response_model=PayableRead)
async def get_payable(payable_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> PayableRead:
    try:
        return await payable_service.get(db, current_user.id, payable_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.patch("/{payable_id}", response_model=PayableRead)
async def update_payable(
    payable_id: uuid.UUID, data: PayableUpdate, current_user: CurrentUser, db: DbSession
) -> PayableRead:
    try:
        return await payable_service.update(db, current_user.id, payable_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc


@router.delete("/{payable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payable(payable_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await payable_service.soft_delete(db, current_user.id, payable_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
