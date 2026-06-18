"""Person (relationship memory) CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page
from app.schemas.person import PersonCreate, PersonRead, PersonUpdate
from app.services import person_service
from app.services.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/persons", tags=["persons"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")


@router.post("", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
async def create_person(data: PersonCreate, current_user: CurrentUser, db: DbSession) -> PersonRead:
    row = await person_service.create(db, current_user.id, data)
    return PersonRead.model_validate(row)


@router.get("", response_model=Page[PersonRead])
async def list_persons(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[PersonRead]:
    rows, total = await person_service.list_(db, current_user.id, limit=limit, offset=offset)
    return Page[PersonRead](
        items=[PersonRead.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{person_id}", response_model=PersonRead)
async def get_person(person_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> PersonRead:
    try:
        row = await person_service.get(db, current_user.id, person_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return PersonRead.model_validate(row)


@router.patch("/{person_id}", response_model=PersonRead)
async def update_person(
    person_id: uuid.UUID, data: PersonUpdate, current_user: CurrentUser, db: DbSession
) -> PersonRead:
    try:
        row = await person_service.update(db, current_user.id, person_id, data)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return PersonRead.model_validate(row)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(person_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        await person_service.soft_delete(db, current_user.id, person_id)
    except ResourceNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
