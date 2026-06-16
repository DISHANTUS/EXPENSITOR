"""Advisor service — builds the daily brief (context block + explanations).

Orchestrates the existing engines via projection_service, then renders advisor
explanations + the life-easier context. Deterministic; no Ollama. Behavioral
explanation is included when a profile is available.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.advisor import explainers
from app.intelligence.advisor.context_block import build_context
from app.intelligence.commentary import context as ctxmod
from app.services import behavior_service, commentary_service, projection_service


async def daily_brief(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    """Context block + guidance/risk/behavior explanations, ready for the UI."""
    scenario = await projection_service.get_scenario(db, user_id, today=today)
    guidance_result, risk_result = await projection_service.compute_guidance_and_risk(
        db, user_id, today=scenario.today
    )
    context = build_context(scenario, guidance_result)

    explanations = [
        explainers.explain_guidance(guidance_result, currency=scenario.base_currency).as_dict(),
        explainers.explain_risk(risk_result, currency=scenario.base_currency).as_dict(),
    ]

    profile = await behavior_service.build_profile(db, user_id, today=scenario.today)
    if profile.confidence == "normal":
        explanations.append(explainers.explain_behavior(profile).as_dict())

    commentary = await commentary_service.narrate(db, user_id, trigger=ctxmod.DAILY_BRIEF, today=scenario.today)
    return {"context": context.as_dict(), "explanations": explanations, "commentary": commentary}


async def dependencies(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    """Derived plan→income dependencies with concise advisor explanations."""
    deps, currency = await projection_service.analyze_dependencies(db, user_id, today=today)
    return {
        "dependencies": [d.as_dict() for d in deps],
        "explanations": [explainers.explain_dependency(d, currency=currency).as_dict() for d in deps],
    }
