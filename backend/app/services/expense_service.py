"""Business logic for completed expenses."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense
from app.models.enums import CategorySource
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services import category_service, currency_service, settings_service
from app.services.exceptions import FieldNotNullableError, ResourceNotFoundError

_NON_NULLABLE_FIELDS = {"original_amount", "original_currency", "expense_date"}


async def _base_currency(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = await settings_service.get_settings(db, user_id)
    return settings.base_currency


async def create(db: AsyncSession, user_id: uuid.UUID, data: ExpenseCreate) -> Expense:
    base_currency = await _base_currency(db, user_id)
    await currency_service.get_currency(db, data.original_currency)
    await category_service.validate_category(db, user_id, data.category_id)
    rate, converted = await currency_service.convert_to_base(
        db, data.original_amount, data.original_currency, base_currency
    )
    row = Expense(
        user_id=user_id,
        category_id=data.category_id,
        original_amount=data.original_amount,
        original_currency=data.original_currency,
        exchange_rate=rate,
        converted_amount=converted,
        base_currency=base_currency,
        description=data.description,
        expense_date=data.expense_date,
        category_source=CategorySource.manual if data.category_id is not None else None,
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
    category_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Expense], int]:
    conditions = [Expense.user_id == user_id, Expense.deleted_at.is_(None)]
    if category_id is not None:
        conditions.append(Expense.category_id == category_id)
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)

    total = await db.scalar(select(func.count()).select_from(Expense).where(*conditions)) or 0
    result = await db.execute(
        select(Expense)
        .where(*conditions)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    result = await db.execute(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.user_id == user_id,
            Expense.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Expense")
    return row


async def update(
    db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID, data: ExpenseUpdate
) -> Expense:
    row = await get(db, user_id, expense_id)
    updates = data.model_dump(exclude_unset=True)

    for field in ("expense_date", "description"):
        if field in updates:
            if updates[field] is None and field in _NON_NULLABLE_FIELDS:
                raise FieldNotNullableError(field)
            setattr(row, field, updates[field])

    if "category_id" in updates:
        await category_service.validate_category(db, user_id, updates["category_id"])
        row.category_id = updates["category_id"]
        row.category_source = (
            CategorySource.manual if updates["category_id"] is not None else None
        )

    currency_changed = "original_currency" in updates
    if currency_changed:
        if updates["original_currency"] is None:
            raise FieldNotNullableError("original_currency")
        await currency_service.get_currency(db, updates["original_currency"])
        row.original_currency = updates["original_currency"]
    if "original_amount" in updates:
        if updates["original_amount"] is None:
            raise FieldNotNullableError("original_amount")
        row.original_amount = updates["original_amount"]
    if currency_changed or "original_amount" in updates:
        rate, converted = await currency_service.convert_to_base(
            db, row.original_amount, row.original_currency, row.base_currency
        )
        row.exchange_rate = rate
        row.converted_amount = converted

    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    row = await get(db, user_id, expense_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
