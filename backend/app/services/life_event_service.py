"""Life-event CRUD (Sprint 6b) — user-entered timeline milestones."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LifeEvent
from app.schemas.life_event import LifeEventCreate
from app.services.exceptions import ResourceNotFoundError


async def create(db: AsyncSession, user_id: uuid.UUID, data: LifeEventCreate) -> LifeEvent:
    row = LifeEvent(user_id=user_id, title=data.title, event_date=data.event_date,
                    kind=data.kind, icon=data.icon, note=data.note)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_(db: AsyncSession, user_id: uuid.UUID) -> list[LifeEvent]:
    return list((await db.execute(
        select(LifeEvent).where(LifeEvent.user_id == user_id, LifeEvent.deleted_at.is_(None))
        .order_by(LifeEvent.event_date))).scalars().all())


async def delete(db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID) -> None:
    row = await db.scalar(select(LifeEvent).where(
        LifeEvent.id == event_id, LifeEvent.user_id == user_id, LifeEvent.deleted_at.is_(None)))
    if row is None:
        raise ResourceNotFoundError("Life event not found")
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
