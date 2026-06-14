"""Seed system (default) expense categories. Idempotent by name."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category

# is_essential flags Emergency Mode's non-cuttable categories (rent, utilities,
# groceries, health). Transportation is discretionary (walk-instead-of-cab).
CATEGORIES: list[dict[str, object]] = [
    {"name": "Food & Dining", "icon": "restaurant", "color": "#FF7043", "is_essential": False},
    {"name": "Groceries", "icon": "shopping_cart", "color": "#66BB6A", "is_essential": True},
    {"name": "Transportation", "icon": "directions_car", "color": "#42A5F5", "is_essential": False},
    {"name": "Rent & Housing", "icon": "home", "color": "#8D6E63", "is_essential": True},
    {"name": "Utilities", "icon": "bolt", "color": "#FFA726", "is_essential": True},
    {"name": "Shopping", "icon": "shopping_bag", "color": "#AB47BC", "is_essential": False},
    {"name": "Entertainment", "icon": "movie", "color": "#EC407A", "is_essential": False},
    {"name": "Health & Medical", "icon": "favorite", "color": "#EF5350", "is_essential": True},
    {"name": "Education", "icon": "school", "color": "#26A69A", "is_essential": False},
    {"name": "Travel", "icon": "flight", "color": "#29B6F6", "is_essential": False},
    {"name": "Subscriptions", "icon": "subscriptions", "color": "#5C6BC0", "is_essential": False},
    {"name": "Personal Care", "icon": "spa", "color": "#9CCC65", "is_essential": False},
    {"name": "Bills & Fees", "icon": "receipt_long", "color": "#78909C", "is_essential": True},
    {"name": "Gifts & Donations", "icon": "card_giftcard", "color": "#D81B60", "is_essential": False},
    {"name": "Miscellaneous", "icon": "category", "color": "#BDBDBD", "is_essential": False},
]


async def seed_categories(session: AsyncSession) -> int:
    """Insert any missing system categories. Returns the number inserted."""
    result = await session.execute(select(Category.name).where(Category.is_system.is_(True)))
    existing = set(result.scalars().all())

    to_add = [
        Category(
            user_id=None,
            name=c["name"],
            icon=c["icon"],
            color=c["color"],
            is_system=True,
            is_essential=bool(c["is_essential"]),
        )
        for c in CATEGORIES
        if c["name"] not in existing
    ]
    session.add_all(to_add)
    return len(to_add)
