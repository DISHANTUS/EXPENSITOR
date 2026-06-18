"""Life-event endpoints (Sprint 6b): user-entered timeline milestones."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.life_event import LifeEventCreate, LifeEventRead
from app.services import life_event_service
from app.services.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/life-events", tags=["life-events"])


@router.post("", response_model=LifeEventRead, status_code=status.HTTP_201_CREATED)
async def create_life_event(data: LifeEventCreate, current_user: CurrentUser, db: DbSession) -> LifeEventRead:
    return LifeEventRead.model_validate(await life_event_service.create(db, current_user.id, data))


@router.get("", response_model=list[LifeEventRead])
async def list_life_events(current_user: CurrentUser, db: DbSession) -> list[LifeEventRead]:
    return [LifeEventRead.model_validate(r) for r in await life_event_service.list_(db, current_user.id)]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_life_event(event_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await life_event_service.delete(db, current_user.id, event_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Life event not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
