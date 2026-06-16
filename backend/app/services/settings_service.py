"""Business logic for user settings (read/update + default creation)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.models import Currency, UserSettings
from app.schemas.settings import UserSettingsUpdate
from app.services.exceptions import FieldNotNullableError, UnsupportedCurrencyError

# Fields that must never be set to NULL via PATCH.
_NON_NULLABLE_FIELDS = {
    "base_currency",
    "timezone",
    "starting_balance",
    "preferred_ai_tone",
    "notification_preferences",
}


def build_default_settings(user_id: uuid.UUID) -> UserSettings:
    """Construct a default settings row for a new user (not yet persisted)."""
    return UserSettings(user_id=user_id, base_currency=app_settings.DEFAULT_BASE_CURRENCY)


async def get_settings(db: AsyncSession, user_id: uuid.UUID) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is None:
        # Safety net: every user should already have settings from registration.
        row = build_default_settings(user_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def update_settings(
    db: AsyncSession, user_id: uuid.UUID, data: UserSettingsUpdate
) -> UserSettings:
    row = await get_settings(db, user_id)
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return row

    if updates.get("base_currency") is not None:
        currency = await db.get(Currency, updates["base_currency"])
        if currency is None:
            raise UnsupportedCurrencyError(updates["base_currency"])

    for field, value in updates.items():
        if value is None and field in _NON_NULLABLE_FIELDS:
            raise FieldNotNullableError(field)
        setattr(row, field, value)

    await db.commit()
    await db.refresh(row)
    return row
