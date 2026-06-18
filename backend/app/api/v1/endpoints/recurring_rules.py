"""Recurring-rule CRUD (subscriptions / EMI / bills / insurance / borrowed)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.recurring_rule import RecurringRuleCreate, RecurringRuleRead, RecurringRuleUpdate
from app.services import recurring_rule_service
from app.services.exceptions import (
    CurrencyNotFoundError,
    InvalidOperationError,
    RateNotAvailableError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/recurring-rules", tags=["recurring-rules"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring rule not found")


def _to_422(exc: Exception) -> HTTPException:
    detail = f"Unsupported currency: {exc.code}" if isinstance(exc, CurrencyNotFoundError) else (
        exc.message if isinstance(exc, InvalidOperationError) else str(exc)
    )
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("", response_model=RecurringRuleRead, status_code=status.HTTP_201_CREATED)
async def create_recurring_rule(
    data: RecurringRuleCreate, current_user: CurrentUser, db: DbSession
) -> RecurringRuleRead:
    try:
        row = await recurring_rule_service.create(db, current_user.id, data)
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc
    return RecurringRuleRead.model_validate(row)


@router.get("", response_model=Page[RecurringRuleRead])
async def list_recurring_rules(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    active_only: bool = Query(default=False),
) -> Page[RecurringRuleRead]:
    rows, total = await recurring_rule_service.list_(
        db, current_user.id, limit=limit, offset=offset, active_only=active_only
    )
    return Page[RecurringRuleRead](
        items=[RecurringRuleRead.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{rule_id}", response_model=RecurringRuleRead)
async def get_recurring_rule(rule_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> RecurringRuleRead:
    try:
        row = await recurring_rule_service.get(db, current_user.id, rule_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return RecurringRuleRead.model_validate(row)


@router.patch("/{rule_id}", response_model=RecurringRuleRead)
async def update_recurring_rule(
    rule_id: uuid.UUID, data: RecurringRuleUpdate, current_user: CurrentUser, db: DbSession
) -> RecurringRuleRead:
    try:
        row = await recurring_rule_service.update(db, current_user.id, rule_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    except (CurrencyNotFoundError, RateNotAvailableError, InvalidOperationError) as exc:
        raise _to_422(exc) from exc
    return RecurringRuleRead.model_validate(row)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_rule(rule_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await recurring_rule_service.soft_delete(db, current_user.id, rule_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
