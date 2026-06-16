"""Business logic for actual income (historical receipts)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Income
from app.models.enums import IncomeSourceType
from app.schemas.income import IncomeCreate, IncomeUpdate
from app.services import currency_service, settings_service
from app.services.exceptions import ResourceNotFoundError


async def _base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = await settings_service.get_settings(db, user_id)
    return settings.base_currency


async def create(db: AsyncSession, user_id: uuid.UUID, data: IncomeCreate) -> Income:
    base_currency = await _base_currency(db, user_id)
    await currency_service.get_currency(db, data.original_currency)  # validate -> 422 if unknown
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, base_currency
    )
    row = Income(
        user_id=user_id,
        source_type=data.source_type,
        original_amount=data.original_amount,
        original_currency=data.original_currency,
        exchange_rate=rate,
        converted_amount=converted,
        base_currency=base_currency,
        description=data.description,
        received_date=data.received_date,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    source_type: IncomeSourceType | None = None,
) -> tuple[list[Income], int]:
    conditions = [Income.user_id == user_id, Income.deleted_at.is_(None)]
    if source_type is not None:
        conditions.append(Income.source_type == source_type)

    total = await db.scalar(select(func.count()).select_from(Income).where(*conditions)) or 0
    result = await db.execute(
        select(Income)
        .where(*conditions)
        .order_by(Income.received_date.desc(), Income.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, income_id: uuid.UUID) -> Income:
    result = await db.execute(
        select(Income).where(
            Income.id == income_id,
            Income.user_id == user_id,
            Income.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Income")
    return row


async def update(
    db: AsyncSession, user_id: uuid.UUID, income_id: uuid.UUID, data: IncomeUpdate
) -> Income:
    row = await get(db, user_id, income_id)
    updates = data.model_dump(exclude_unset=True)

    for field in ("source_type", "received_date", "description"):
        if field in updates:
            setattr(row, field, updates[field])

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

    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, income_id: uuid.UUID) -> None:
    row = await get(db, user_id, income_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
