"""Financial Health Score service (C8): build the BehavioralProfile once, then
aggregate it into the multi-dimensional health score. Compute-on-read, stateless;
no new financial math (reuses the profile exclusively)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.health import HealthScore, build_health_score
from app.services import behavior_service


async def get_score(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> HealthScore:
    profile = await behavior_service.build_profile(db, user_id, today=today)
    return build_health_score(profile)


async def build(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    return (await get_score(db, user_id, today=today)).as_dict()
