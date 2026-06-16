"""Daily budget session endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.enums import BudgetSessionStatus
from app.schemas.budget_session import (
    BudgetSessionCreate,
    BudgetSessionUpdate,
    LinkExpenseRequest,
    SessionRead,
)
from app.schemas.common import Page
from app.services import budget_session_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/budget-sessions", tags=["budget-sessions"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget session not found")


def _to_422(exc: Exception) -> HTTPException:
    if isinstance(exc, CurrencyNotFoundError):
        detail = f"Unsupported currency: {exc.code}"
    elif isinstance(exc, InvalidOperationError):
        detail = exc.message
    else:
        detail = str(exc)
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(data: BudgetSessionCreate, current_user: CurrentUser, db: DbSession) -> SessionRead:
    try:
        return await budget_session_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _to_422(exc) from exc


@router.get("", response_model=Page[SessionRead])
async def list_sessions(
    current_user: CurrentUser,
    db: DbSession,
    status_filter: BudgetSessionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[SessionRead]:
    items, total = await budget_session_service.list_(
        db, current_user.id, status=status_filter, limit=limit, offset=offset
    )
    return Page[SessionRead](items=items, total=total, limit=limit, offset=offset)


# Declared before /{session_id} so "active" isn't parsed as a UUID.
@router.get("/active", response_model=list[SessionRead])
async def list_active_sessions(current_user: CurrentUser, db: DbSession) -> list[SessionRead]:
    return await budget_session_service.list_active(db, current_user.id)


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> SessionRead:
    try:
        return await budget_session_service.get(db, current_user.id, session_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: uuid.UUID, data: BudgetSessionUpdate, current_user: CurrentUser, db: DbSession
) -> SessionRead:
    try:
        return await budget_session_service.update(db, current_user.id, session_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise _to_422(exc) from exc


@router.post("/{session_id}/expenses", response_model=SessionRead)
async def link_expense(
    session_id: uuid.UUID, data: LinkExpenseRequest, current_user: CurrentUser, db: DbSession
) -> SessionRead:
    try:
        return await budget_session_service.link_expense(db, current_user.id, session_id, data.expense_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except InvalidOperationError as exc:
        raise _to_422(exc) from exc


@router.delete("/{session_id}/expenses/{expense_id}", response_model=SessionRead)
async def unlink_expense(
    session_id: uuid.UUID, expense_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> SessionRead:
    try:
        return await budget_session_service.unlink_expense(db, current_user.id, session_id, expense_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.post("/{session_id}/complete", response_model=SessionRead)
async def complete_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> SessionRead:
    try:
        return await budget_session_service.complete(db, current_user.id, session_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except InvalidOperationError as exc:
        raise _to_422(exc) from exc


@router.post("/{session_id}/cancel", response_model=SessionRead)
async def cancel_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> SessionRead:
    try:
        return await budget_session_service.cancel(db, current_user.id, session_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await budget_session_service.soft_delete(db, current_user.id, session_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
