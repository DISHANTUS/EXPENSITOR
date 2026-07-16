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
from app.services import (
    analytics_service,
    behavior_service,
    commentary_service,
    projection_service,
    spending_pattern_service,
)


async def _today_snapshot(db: AsyncSession, user_id: uuid.UUID, today: date, currency: str) -> dict[str, Any]:
    """Actual today-spend, by category — the compact Home view's "spent today"
    list. Distinct from context.daily_remaining, which is a forward allowance,
    not a sum of what's already been spent (see analytics_service._category_sums)."""
    by_category = await analytics_service._category_sums(db, user_id, today, today)  # noqa: SLF001
    items = sorted(
        ({"label": label, "amount": float(amount)} for label, amount in by_category.items()),
        key=lambda i: i["amount"], reverse=True,
    )
    return {
        "currency": currency,
        "spent_today": float(sum(by_category.values())),
        "spent_today_by_category": items,
    }


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
    snapshot = await _today_snapshot(db, user_id, scenario.today, scenario.base_currency)
    # Derive-on-read, like everything else here: opportunistically check for a
    # sustained category shift each time the brief loads. record_advice()'s own
    # 30-day dedup keeps this from ever spamming — see spending_pattern_service.
    shifts = await spending_pattern_service.detect_and_record_shifts(
        db, user_id, today=scenario.today, base_currency=scenario.base_currency
    )
    return {
        "context": context.as_dict(), "explanations": explanations, "commentary": commentary,
        "today_snapshot": snapshot, "spending_shifts_detected": len(shifts),
    }


async def dependencies(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    """Derived plan→income dependencies with concise advisor explanations."""
    deps, currency = await projection_service.analyze_dependencies(db, user_id, today=today)
    return {
        "dependencies": [d.as_dict() for d in deps],
        "explanations": [explainers.explain_dependency(d, currency=currency).as_dict() for d in deps],
    }
