"""Preference endpoints (C7b): view and edit the adaptive policy."""

from __future__ import annotations

from app.api.deps import CurrentUser, DbSession
from app.schemas.preference import PolicyOut, PreferenceUpdate
from app.services import preference_service

from fastapi import APIRouter

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PolicyOut)
async def get_preferences(current_user: CurrentUser, db: DbSession) -> PolicyOut:
    row = await preference_service.get_policy(db, current_user.id)
    return PolicyOut(policy=row.policy)


@router.patch("", response_model=PolicyOut)
async def update_preferences(data: PreferenceUpdate, current_user: CurrentUser, db: DbSession) -> PolicyOut:
    row = await preference_service.update_policy(
        db, current_user.id, excluded_levers=data.excluded_levers,
        preferred_levers=data.preferred_levers, flags=data.flags,
    )
    return PolicyOut(policy=row.policy)
