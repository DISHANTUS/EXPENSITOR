"""Category helpers shared by expense and planned-expense services."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category
from app.services.exceptions import InvalidOperationError


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Category]:
    """Categories the user can pick: system categories (user_id NULL) plus any
    they own. System categories first, then alphabetical."""
    result = await db.execute(
        select(Category)
        .where(or_(Category.user_id.is_(None), Category.user_id == user_id))
        .order_by(Category.is_system.desc(), Category.name.asc())
    )
    return list(result.scalars().all())


async def validate_category(
    db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID | None
) -> None:
    """Ensure a category is usable by the user: a system category (user_id NULL)
    or one the user owns. No-op when category_id is None."""
    if category_id is None:
        return
    category = await db.get(Category, category_id)
    if category is None or (category.user_id is not None and category.user_id != user_id):
        raise InvalidOperationError("Invalid category")
