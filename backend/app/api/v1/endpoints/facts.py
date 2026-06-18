"""Fun-facts endpoints — the companion's fallback content (orb + Home card).

Facts carry nothing user-specific; the client caches packs for offline use and
falls back to a bundled starter pack when the backend is unreachable.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser
from app.schemas.facts import FactCategoryOut, FactOut, FactPackOut
from app.services import facts_service

router = APIRouter(prefix="/facts", tags=["facts"])


def _categories(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [c.strip() for c in raw.split(",") if c.strip()] or None


@router.get("/categories", response_model=list[FactCategoryOut], summary="Fact categories + counts")
async def list_categories(current_user: CurrentUser) -> list[FactCategoryOut]:
    return [FactCategoryOut(key=c.key, label=c.label, emoji=c.emoji, count=c.count)
            for c in facts_service.categories()]


@router.get("/pack/{key}", response_model=FactPackOut, summary="All facts in a category (for offline cache)")
async def get_pack(key: str, current_user: CurrentUser) -> FactPackOut:
    facts = facts_service.pack(key)
    if not facts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown fact category")
    cat = next((c for c in facts_service.categories() if c.key == key), None)
    return FactPackOut(category=key, category_label=cat.label if cat else key,
                       emoji=cat.emoji if cat else "💡", facts=facts)


@router.get("/random", response_model=FactOut, summary="A fresh random fact (orb single-tap)")
async def random_fact(
    current_user: CurrentUser,
    categories: str | None = Query(default=None, description="Comma-separated category keys to draw from"),
) -> FactOut:
    fact = facts_service.random_fact(_categories(categories))
    if fact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No facts available")
    return FactOut(text=fact.text, category=fact.category,
                   category_label=fact.category_label, emoji=fact.emoji)


@router.get("/daily", response_model=FactOut, summary="Today's deterministic fact (Home card)")
async def daily_fact(
    current_user: CurrentUser,
    day: date | None = Query(default=None, alias="date", description="Device-local date; defaults to server today"),
    categories: str | None = Query(default=None),
) -> FactOut:
    fact = facts_service.daily_fact(day or date.today(), _categories(categories))
    if fact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No facts available")
    return FactOut(text=fact.text, category=fact.category,
                   category_label=fact.category_label, emoji=fact.emoji)
