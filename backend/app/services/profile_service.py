"""Financial profile read/update (Budget Intelligence System).

One row per user, created lazily. Every field is editable anytime — including
later, by talking to Advary — so the user is never trapped in old answers.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FinancialProfile
from app.schemas.financial_profile import FinancialProfileUpdate


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> FinancialProfile:
    row = await db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    if row is None:
        row = FinancialProfile(user_id=user_id)
        db.add(row)
        try:
            await db.commit()
            await db.refresh(row)
        except IntegrityError:
            # Concurrent first-read (e.g. feasibility + recommendations fired together)
            # already created it — roll back and use the existing row.
            await db.rollback()
            row = await db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    return row


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, data: FinancialProfileUpdate
) -> FinancialProfile:
    row = await get_profile(db, user_id)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row
