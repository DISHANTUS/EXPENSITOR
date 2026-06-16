"""Category listing endpoint (read-only picker for expense entry)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.category import CategoryRead
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead], summary="List categories the user can pick")
async def list_categories(current_user: CurrentUser, db: DbSession) -> list[CategoryRead]:
    rows = await category_service.list_for_user(db, current_user.id)
    return [CategoryRead.model_validate(row) for row in rows]
