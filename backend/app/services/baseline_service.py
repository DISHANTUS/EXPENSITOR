"""Country baseline service (Budget Intelligence System — Phase 6).

Hybrid: a bundled dataset is the source of truth (app works offline from first run);
an optional best-effort web refresh can update a cache later. Refresh NEVER blocks
or breaks onboarding — on failure we silently fall back to the bundled baseline.
The user's real spending is always the ultimate truth; baselines are context only.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.budget import country_baselines
from app.schemas.country_baseline import CountryBaseline
from app.services import profile_service


async def _try_web_refresh(country: str) -> dict | None:
    """Best-effort, pluggable. No external cost-of-living provider is wired yet
    (and none is required — bundled data is authoritative), so this returns None
    and we fall back to bundled. A future provider can populate + cache here
    without changing callers."""
    return None


async def get_baseline(db: AsyncSession, user_id: uuid.UUID, *, refresh: bool = False) -> CountryBaseline:
    profile = await profile_service.get_profile(db, user_id)
    data = country_baselines.lookup(profile.current_country, profile.life_stage)

    if refresh and profile.current_country:
        try:
            fetched = await _try_web_refresh(profile.current_country)
            if fetched:
                data = {**data, **fetched, "source": "refreshed"}
        except Exception:
            pass  # never break the flow — keep the bundled baseline

    return CountryBaseline.model_validate(data)
