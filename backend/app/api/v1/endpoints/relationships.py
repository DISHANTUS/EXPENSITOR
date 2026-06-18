"""Relationship-page endpoints (Sprint 7): GET /relationships | /relationships/{name}."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.relationship import RelationshipDetail, RelationshipList
from app.services import relationship_service

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.get("", response_model=RelationshipList, summary="People you track, with memory counts + trust")
async def list_relationships(current_user: CurrentUser, db: DbSession) -> RelationshipList:
    return RelationshipList(people=await relationship_service.list_people(db, current_user.id))


@router.get("/{name}", response_model=RelationshipDetail, summary="A person's story: timeline, memories, trust, plans")
async def relationship_detail(name: str, current_user: CurrentUser, db: DbSession) -> RelationshipDetail:
    return await relationship_service.detail(db, current_user.id, name)
