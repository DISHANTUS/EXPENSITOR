"""Person (relationship) CRUD + ownership validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person
from app.schemas.person import PersonCreate, PersonUpdate
from app.services.exceptions import InvalidOperationError, ResourceNotFoundError


async def create(db: AsyncSession, user_id: uuid.UUID, data: PersonCreate) -> Person:
    row = Person(user_id=user_id, **data.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(db: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int) -> tuple[list[Person], int]:
    conditions = [Person.user_id == user_id, Person.deleted_at.is_(None)]
    total = await db.scalar(select(func.count()).select_from(Person).where(*conditions)) or 0
    result = await db.execute(
        select(Person).where(*conditions).order_by(Person.name.asc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total)


async def get(db: AsyncSession, user_id: uuid.UUID, person_id: uuid.UUID) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id, Person.deleted_at.is_(None))
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError("Person")
    return row


async def update(db: AsyncSession, user_id: uuid.UUID, person_id: uuid.UUID, data: PersonUpdate) -> Person:
    row = await get(db, user_id, person_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


async def soft_delete(db: AsyncSession, user_id: uuid.UUID, person_id: uuid.UUID) -> None:
    row = await get(db, user_id, person_id)
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def validate_person(db: AsyncSession, user_id: uuid.UUID, person_id: uuid.UUID | None) -> None:
    """Ensure a referenced person belongs to the user. No-op when None."""
    if person_id is None:
        return
    row = await db.get(Person, person_id)
    if row is None or row.user_id != user_id or row.deleted_at is not None:
        raise InvalidOperationError("Invalid person")
