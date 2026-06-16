"""Commentary service (C5): assemble a single `CommentaryContext` from
already-computed intelligence, then run the deterministic renderer.

This is the one reusable entry point the Assistant, Advisor brief, Recommendations
and (Phase 3b) Ollama all call. It performs NO financial math — every input comes
from an existing engine/service. Compute-on-read, stateless.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.intelligence.advisor import explainers
from app.intelligence.advisor.context_block import build_context as build_life_context
from app.intelligence.behavior.insights import InsightContext, build_behavioral_insights
from app.intelligence.commentary import (
    COMMENTARY_SCHEMA_VERSION,
    GROUNDING_VERSION,
    ActionPreview,
    CommentaryContext,
    render_commentary,
)
from app.intelligence.health import build_health_score
from app.intelligence.projection import dependency
from app.models import Expense, Income, IncomeSource, Receivable
from app.services import behavior_service, preference_service, projection_service, recommendation_service


async def _has_activity(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Cold-start signal (A9): any recorded spending/income means we have something
    real to talk about. Calendar months in the profile window are NOT activity."""
    if await db.scalar(select(exists().where(Expense.user_id == user_id, Expense.deleted_at.is_(None)))):
        return True
    return bool(await db.scalar(select(exists().where(Income.user_id == user_id, Income.deleted_at.is_(None)))))


# --- source-label resolution (read-only; never invents) ---------------------
async def _source_maps(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[dict[uuid.UUID, IncomeSource], dict[uuid.UUID, Receivable]]:
    isrcs = (await db.execute(
        select(IncomeSource).where(IncomeSource.user_id == user_id, IncomeSource.deleted_at.is_(None)))).scalars().all()
    recvs = (await db.execute(
        select(Receivable).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None)))).scalars().all()
    return {s.id: s for s in isrcs}, {r.id: r for r in recvs}


def _resolve_label(origin: str | None, source_id: Any, isrc_map: dict, recv_map: dict) -> tuple[str | None, str | None]:
    """Map (origin, source_id) -> (human source label, exact-time ISO) or (None, None)."""
    try:
        sid = source_id if isinstance(source_id, uuid.UUID) else uuid.UUID(str(source_id))
    except (ValueError, TypeError):
        return None, None
    if origin and origin.startswith("income_source:"):
        src = isrc_map.get(sid)
        exact = src.expected_time.isoformat() if (src and src.expected_time) else None
        kind = origin.split(":", 1)[1]
        if kind == "salary":
            return "your salary", exact
        return (src.label if src else None), exact
    if origin == "receivable":
        r = recv_map.get(sid)
        if r is None:
            return None, None
        label = f"your {r.source_name.lower()}" if (r.source_type and r.source_type.value == "family") else r.source_name
        return label, (r.expected_time.isoformat() if r.expected_time else None)
    return None, None


# --- context assembly -------------------------------------------------------
async def build_context(
    db: AsyncSession, user_id: uuid.UUID, *, trigger: str, today: date | None = None,
    headline_hint: str | None = None, action_preview: ActionPreview | None = None,
) -> CommentaryContext:
    scenario = await projection_service.get_scenario(db, user_id, today=today)
    guidance, risk = await projection_service.compute_guidance_and_risk(db, user_id, today=scenario.today)
    context_block = build_life_context(scenario, guidance).as_dict()

    profile = await behavior_service.build_profile(db, user_id, today=scenario.today)
    has_history = await _has_activity(db, user_id)

    isrc_map, recv_map = await _source_maps(db, user_id)

    # dependencies — enriched with a human source label + exact time when known
    dep_dicts: list[dict[str, Any]] = []
    for d in dependency.analyze(scenario):
        dd = d.as_dict()
        label, exact = _resolve_label(dd.get("income_origin"), dd.get("income_source_id"), isrc_map, recv_map)
        if label:
            dd["source_label"] = label
        if exact:
            dd["income_time_exact"] = exact
        dep_dicts.append(dd)

    # goals — reuse the canonical savings evaluation (single source of truth)
    net = await recommendation_service._net_so_far(db, user_id, scenario.today)
    goal_states = await recommendation_service._goal_states(db, user_id, scenario, net)
    goal_dicts = [{"kind": gs.kind, "name": gs.name, "status": gs.status,
                   "shortfall": str(gs.shortfall), "target_date": gs.target_date} for gs in goal_states]

    # next expected inflow (strictly future, sorted) — with resolved source label
    next_income = None
    ev = scenario.income_events[0] if scenario.income_events else None
    if ev is not None:
        label, _ = _resolve_label(ev.origin, ev.source_id, isrc_map, recv_map)
        next_income = {
            "amount": str(ev.amount_base), "currency": scenario.base_currency, "date": ev.date.isoformat(),
            "window": ev.time_window, "exact": (ev.exact_time.isoformat() if ev.exact_time else None),
            "source_label": label,
        }

    insights = build_behavioral_insights(profile, context=InsightContext(
        goals=tuple((g["kind"], g["name"]) for g in goal_dicts), dependencies=tuple(dep_dicts)))

    rec_result = await recommendation_service.build(db, user_id, today=scenario.today)
    policy = (await preference_service.get_policy(db, user_id)).policy or {}

    explanations = [
        explainers.explain_guidance(guidance, currency=scenario.base_currency).as_dict(),
        explainers.explain_risk(risk, currency=scenario.base_currency).as_dict(),
    ]
    if profile.confidence == "normal":
        explanations.append(explainers.explain_behavior(profile).as_dict())

    return CommentaryContext(
        currency=scenario.base_currency, trigger=trigger, confidence=profile.confidence,
        has_history=has_history, headline_hint=headline_hint, context=context_block,
        explanations=tuple(explanations), behavioral_insights=tuple(i.as_dict() for i in insights),
        recommendations=tuple(rec_result["recommendations"]), bundles=tuple(rec_result["bundles"]),
        dependencies=tuple(dep_dicts), goals=tuple(goal_dicts), next_income=next_income,
        risk={"risk_level": risk.risk_level, "min_expected_balance": str(risk.min_expected_balance),
              "min_expected_balance_date": risk.min_expected_balance_date.isoformat()},
        policy_influence=rec_result.get("policy_influence", {}),
        alternatives_applied=bool(rec_result.get("alternatives_applied", False)),
        policy_provenance=policy.get("provenance", {}),
        protect_emotional=bool(policy.get("flags", {}).get("protect_emotional_critical", False)),
        action_preview=action_preview,
        health_score=build_health_score(profile).as_dict(),   # C8: facts lead, score summarizes
    )


async def narrate(
    db: AsyncSession, user_id: uuid.UUID, *, trigger: str, today: date | None = None,
    expand: bool = False, headline_hint: str | None = None, action_preview: ActionPreview | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """Single-voice commentary for a surface.

    Returns an envelope whose `deterministic_commentary` is the canonical source of
    truth. When OLLAMA_ENABLED, an optional `narrated_commentary` (presentation only)
    is added if it passes the grounding guard; otherwise the deterministic text stands
    and the user never notices the difference (B5/B7/B10)."""
    ctx = await build_context(
        db, user_id, trigger=trigger, today=today, headline_hint=headline_hint, action_preview=action_preview)
    deterministic = render_commentary(ctx, expand=expand).as_dict()

    envelope: dict[str, Any] = {
        "deterministic_commentary": deterministic,
        "narrated_commentary": None,
        "narration_source": "deterministic",
        "narration_status": "disabled",
        "grounding_version": GROUNDING_VERSION,
        "commentary_schema_version": COMMENTARY_SCHEMA_VERSION,
    }
    if settings.OLLAMA_ENABLED:
        from app.services import ollama_service  # lazy: only import the I/O layer when enabled
        outcome = await ollama_service.narrate_commentary(deterministic, style=style)
        envelope["narration_status"] = outcome["status"]
        if outcome["ok"]:
            envelope["narrated_commentary"] = outcome["narrated"]
            envelope["narration_source"] = "ollama"
    return envelope
