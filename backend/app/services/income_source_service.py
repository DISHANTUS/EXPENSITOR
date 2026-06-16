"""Business logic for income sources (expected income)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IncomeSource
from app.models.enums import IncomeKind, IncomeSourceType
from app.schemas.income_source import IncomeSourceCreate, IncomeSourceUpdate
from app.services import currency_service, settings_service
from app.services.exceptions import InvalidOperationError, ResourceNotFoundError

_SIMPLE_FIELDS = ("label", "source_type", "kind", "reliability", "is_active", "expected_time_window")


async def _base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = await settings_service.get_settings(db, user_id)
    return settings.base_currency


def _validate_kind_consistency(row: IncomeSource) -> None:
    """Enforce recurrence_day/expected_date based on kind; normalize the other."""
    if row.kind == IncomeKind.recurring:
        if row.recurrence_day is None:
            raise InvalidOperationError("recurrence_day is required for recurring income sources")
        row.expected_date = None
    else:  # one_time
        if row.expected_date is None:
            raise InvalidOperationError("expected_date is required for one-time income sources")
        row.recurrence_day = None


async def create(db: AsyncSession, user_id: uuid.UUID, data: IncomeSourceCreate) -> IncomeSource:
    base_currency = await _base_currency(db, user_id)
    await currency_service.get_currency(db, data.original_currency)  # validate -> 422 if unknown
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, base_currency
    )
    row = IncomeSource(
        user_id=user_id,
        label=data.label,
        source_type=data.source_type,
        kind=data.kind,
        original_amount=data.original_amount,
        original_currency=data.original_currency,
        exchange_rate=rate,
        converted_amount=converted,
        base_currency=base_currency,
        recurrence_day=data.recurrence_day,
        expected_date=data.expected_date,
        reliability=data.reliability,
        is_active=data.is_active,
        expected_time_window=data.expected_time_window,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    is_active: bool | None = None,
    source_type: IncomeSourceType | None = None,
    kind: IncomeKind | None = None,
) -> list[IncomeSource]:
    stmt = select(IncomeSource).where(
        IncomeSource.user_id == user_id, IncomeSource.deleted_at.is_(None)
    )
    if is_active is not None:
        stmt = stmt.where(IncomeSource.is_active == is_active)
    if source_type is not None:
        stmt = stmt.where(IncomeSource.source_type == source_type)
    if kind is not None:
        stmt = stmt.where(IncomeSource.kind == kind)
    stmt = stmt.order_by(IncomeSource.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get(db: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID) -> IncomeSource:
    result = await db.execute(
        select(IncomeSource).where(
            IncomeSource.id == source_id,
            IncomeSource.user_id == user_id,
            IncomeSource.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Income source")
    return row


async def update(
    db: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID, data: IncomeSourceUpdate
) -> IncomeSource:
    row = await get(db, user_id, source_id)
    updates = data.model_dump(exclude_unset=True)

    for field in _SIMPLE_FIELDS:
        if field in updates:
            setattr(row, field, updates[field])
    if "recurrence_day" in updates:
        row.recurrence_day = updates["recurrence_day"]
    if "expected_date" in updates:
        row.expected_date = updates["expected_date"]

    currency_changed = updates.get("original_currency") is not None
    if currency_changed:
        await currency_service.get_currency(db, updates["original_currency"])
        row.original_currency = updates["original_currency"]
    if updates.get("original_amount") is not None:
        row.original_amount = updates["original_amount"]
    if currency_changed or updates.get("original_amount") is not None:
        rate, converted = await currency_service.convert_to_base(
            db, row.original_amount, row.original_currency, row.base_currency
        )
        row.exchange_rate = rate
        row.converted_amount = converted

    _validate_kind_consistency(row)

    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID) -> None:
    row = await get(db, user_id, source_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
