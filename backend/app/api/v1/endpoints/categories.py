"""Category listing endpoint (read-only picker for expense entry)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.category import CategoryCreate, CategoryRead
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead], summary="List categories the user can pick")
async def list_categories(current_user: CurrentUser, db: DbSession) -> list[CategoryRead]:
    rows = await category_service.list_for_user(db, current_user.id)
    return [CategoryRead.model_validate(row) for row in rows]


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED,
             summary="Create a custom category (Other -> specify)")
async def create_category(data: CategoryCreate, current_user: CurrentUser, db: DbSession) -> CategoryRead:
    row = await category_service.create_for_user(
        db, current_user.id, name=data.name, icon=data.icon, color=data.color, is_essential=data.is_essential
    )
    return CategoryRead.model_validate(row)
