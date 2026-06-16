"""Behavioral Intelligence service (C6/B1).

Owns the timezone derivation of `today`, loads the bounded BehaviorData bundle
once, and builds the deterministic BehavioralProfile. No HTTP endpoints in B1 —
the profile is consumed in-process by Companion (B2) and the advisor engines.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importing the package registers all metrics on the registry.
import app.intelligence.behavior  # noqa: F401
from app.intelligence.behavior.data import load_behavior_data
from app.intelligence.behavior.profile import BehavioralProfile
from app.intelligence.behavior.scoring import build_profile_from_data
from app.models import UserSettings


async def _today_for(db: AsyncSession, user_id: uuid.UUID) -> date:
    tz = await db.scalar(select(UserSettings.timezone).where(UserSettings.user_id == user_id))
    return datetime.now(ZoneInfo(tz or "UTC")).date()


async def build_profile(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> BehavioralProfile:
    if today is None:
        today = await _today_for(db, user_id)
    data = await load_behavior_data(db, user_id, today)
    return build_profile_from_data(data)
