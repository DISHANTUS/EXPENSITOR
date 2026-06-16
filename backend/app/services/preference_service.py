"""Preference Memory & Adaptive Planning (C7b).

Records recommendation feedback and derives a per-user policy that RERANKS /
EXCLUDES / BOOSTS recommendation options. Deterministic aggregation (no ML).

CRITICAL: the policy affects recommendation ORDERING only. It never changes any
financial fact (affordability, risk, dependencies, balances, savings) and never
auto-executes an action.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanionEvent, RecommendationFeedback, UserPolicy
from app.models.enums import (
    CompanionEntityType,
    CompanionEventType,
    RecommendationAction,
    RejectionReason,
)

# graded exclusion thresholds (weighted rejects)
_SOFT_THRESHOLD = 2
_STRONG_THRESHOLD = 3
_EMOTIONAL_WEIGHT = 2          # a reject on a high-emotional item counts double (D12)
SOFT_DOWNRANK = 0.25          # soft-excluded score multiplier (heavy down-rank)
_BOOST_MIN, _BOOST_MAX = 0.05, 0.20


def _default_policy() -> dict[str, Any]:
    return {"lever_stats": {}, "explicit_excluded": [], "explicit_preferred": [],
            "flags": {"protect_emotional_critical": False}, "provenance": {}}


async def get_policy(db: AsyncSession, user_id: uuid.UUID) -> UserPolicy:
    row = await db.scalar(select(UserPolicy).where(UserPolicy.user_id == user_id))
    if row is None:
        row = UserPolicy(user_id=user_id, policy=_default_policy())
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _split(recommendation_id: str) -> tuple[str, str]:
    category, _, lever = recommendation_id.partition(":")
    return category, (lever or recommendation_id)


# --- derivation (pure over the policy dict) ---------------------------------
def _lever_state(stats: dict[str, int]) -> tuple[str, float]:
    """Return (state, boost): state ∈ none|soft|strong|preferred."""
    a = stats.get("accepted", 0)
    r = stats.get("rejected", 0)
    d = stats.get("deferred", 0)
    er = stats.get("emotional_rejects", 0)
    weighted_rejects = r + er * (_EMOTIONAL_WEIGHT - 1)  # emotional rejects escalate
    total = a + r + d
    if a > weighted_rejects and a >= 1:           # net-positive → preferred (acceptance overrides)
        rate = a / total if total else 1.0
        boost = min(_BOOST_MAX, max(_BOOST_MIN, _BOOST_MIN + (_BOOST_MAX - _BOOST_MIN) * rate))
        return "preferred", round(boost, 4)
    if weighted_rejects >= _STRONG_THRESHOLD:
        return "strong", 0.0
    if weighted_rejects >= _SOFT_THRESHOLD:
        return "soft", 0.0
    return "none", 0.0


def policy_levers(policy: dict[str, Any]) -> dict[str, Any]:
    """Effective strong/soft excludes + boosts (the only thing rankers consume)."""
    strong: set[str] = set(policy.get("explicit_excluded", []))
    soft: set[str] = set()
    boosts: dict[str, float] = {lever: _BOOST_MAX for lever in policy.get("explicit_preferred", [])}
    for lever, stats in policy.get("lever_stats", {}).items():
        if lever in strong:
            continue
        state, boost = _lever_state(stats)
        if state == "strong":
            strong.add(lever)
        elif state == "soft":
            soft.add(lever)
        elif state == "preferred":
            boosts.setdefault(lever, boost)
    return {"strong": strong, "soft": soft - strong, "boosts": boosts}


# levers that also map to C7a decision strategy kinds
_LEVER_TO_STRATEGY = {"use_savings": "use_savings", "wait_for_income": "wait_for_income", "move_date": "move_date"}


def excluded_strategies(policy: dict[str, Any]) -> tuple[str, ...]:
    strong = policy_levers(policy)["strong"]
    out = set()
    for lever in strong:
        if lever in _LEVER_TO_STRATEGY:
            out.add(_LEVER_TO_STRATEGY[lever])
        elif lever.startswith("reduce_"):
            out.add("reduce_discretionary")
    return tuple(sorted(out))


# --- mutations (record / edit) ----------------------------------------------
async def record_feedback(
    db: AsyncSession, user_id: uuid.UUID, *, recommendation_id: str, action: RecommendationAction,
    reason: RejectionReason | None = None, reason_context: str | None = None,
    emotional_importance: str | None = None, note: str | None = None,
) -> UserPolicy:
    category, lever = _split(recommendation_id)
    is_emotional = (emotional_importance or "").lower() in ("high", "critical")

    db.add(RecommendationFeedback(
        user_id=user_id, recommendation_id=recommendation_id, lever_key=lever, category=category,
        action=action, reason=reason, reason_context=reason_context,
        emotional_importance=emotional_importance, note=note,
    ))
    db.add(CompanionEvent(
        user_id=user_id, event_type=CompanionEventType.action_completed, surface="recommendations",
        action=action.value, entity_type=CompanionEntityType.recommendation, entity_id=None,
        payload={"recommendation_id": recommendation_id, "reason": reason.value if reason else None},
    ))

    policy_row = await get_policy(db, user_id)
    policy = dict(policy_row.policy or _default_policy())
    stats = dict(policy.setdefault("lever_stats", {}))
    s = dict(stats.get(lever, {"accepted": 0, "rejected": 0, "deferred": 0, "emotional_rejects": 0}))
    s[action.value] = s.get(action.value, 0) + 1
    if action == RecommendationAction.rejected and is_emotional:
        s["emotional_rejects"] = s.get("emotional_rejects", 0) + 1
        policy.setdefault("flags", {})["protect_emotional_critical"] = True
    stats[lever] = s
    policy["lever_stats"] = stats

    prov = dict(policy.setdefault("provenance", {}))
    prov[lever] = {"reason": reason.value if reason else action.value, "reason_context": reason_context}
    policy["provenance"] = prov

    policy_row.policy = policy
    # SQLAlchemy needs an explicit reassignment for JSONB mutation tracking.
    await db.execute(
        UserPolicy.__table__.update().where(UserPolicy.id == policy_row.id).values(policy=policy)
    )
    await db.commit()
    await db.refresh(policy_row)
    return policy_row


async def update_policy(
    db: AsyncSession, user_id: uuid.UUID, *, excluded_levers: list[str] | None = None,
    preferred_levers: list[str] | None = None, flags: dict[str, Any] | None = None,
) -> UserPolicy:
    policy_row = await get_policy(db, user_id)
    policy = dict(policy_row.policy or _default_policy())
    if excluded_levers is not None:
        policy["explicit_excluded"] = sorted(set(excluded_levers))
    if preferred_levers is not None:
        policy["explicit_preferred"] = sorted(set(preferred_levers))
    if flags is not None:
        policy.setdefault("flags", {}).update(flags)
    await db.execute(UserPolicy.__table__.update().where(UserPolicy.id == policy_row.id).values(policy=policy))
    await db.commit()
    await db.refresh(policy_row)
    return policy_row
