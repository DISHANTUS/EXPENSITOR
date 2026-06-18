"""Category helpers shared by expense and planned-expense services."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category
from app.services.exceptions import InvalidOperationError


async def create_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, name: str, icon: str | None = None,
    color: str | None = None, is_essential: bool = False,
) -> Category:
    """Create a user-owned category. Idempotent by name: if the user already has
    one with this name (or a system category matches), return that instead of
    erroring — so repeating an 'Other → specify' value reuses the same category."""
    existing = await db.scalar(
        select(Category).where(
            Category.name == name,
            or_(Category.user_id == user_id, Category.user_id.is_(None)),
        ).limit(1)
    )
    if existing is not None:
        return existing
    row = Category(user_id=user_id, name=name, icon=icon, color=color, is_system=False, is_essential=is_essential)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


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
