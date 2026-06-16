"""Tests for preference_service policy derivation + feedback recording (C7b)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecommendationFeedback, User
from app.models.enums import RecommendationAction, RejectionReason
from app.services import preference_service as ps


def _policy(stats=None, excl=None, pref=None):
    return {"lever_stats": stats or {}, "explicit_excluded": excl or [],
            "explicit_preferred": pref or [], "flags": {}, "provenance": {}}


# --- pure derivation (D8/D10/D12) -------------------------------------------
def test_soft_at_two_strong_at_three_rejects():
    assert "move_date" in ps.policy_levers(_policy({"move_date": {"rejected": 2}}))["soft"]
    strong = ps.policy_levers(_policy({"move_date": {"rejected": 3}}))["strong"]
    assert "move_date" in strong


def test_one_reject_does_not_exclude():
    levers = ps.policy_levers(_policy({"move_date": {"rejected": 1}}))
    assert "move_date" not in levers["soft"] and "move_date" not in levers["strong"]


def test_acceptance_rate_boost_orders_by_rate():
    high = ps.policy_levers(_policy({"x": {"accepted": 8, "rejected": 1}}))["boosts"]["x"]
    low = ps.policy_levers(_policy({"x": {"accepted": 2, "rejected": 1}}))["boosts"]["x"]
    assert 0.05 <= low < high <= 0.20


def test_emotional_reject_escalates_to_soft():
    # a single high-emotional reject escalates (D12): weighted = 1 + 1 = 2 -> soft
    levers = ps.policy_levers(_policy({"move_date": {"rejected": 1, "emotional_rejects": 1}}))
    assert "move_date" in levers["soft"]


def test_acceptance_overrides_exclusion():
    levers = ps.policy_levers(_policy({"x": {"accepted": 5, "rejected": 3}}))
    assert "x" not in levers["strong"] and "x" in levers["boosts"]


def test_explicit_excluded_and_preferred():
    levers = ps.policy_levers(_policy(excl=["use_savings"], pref=["reduce_food"]))
    assert "use_savings" in levers["strong"] and levers["boosts"]["reduce_food"] == 0.20


def test_excluded_strategies_mapping():
    strat = set(ps.excluded_strategies(_policy(excl=["use_savings", "reduce_food", "move_date"])))
    assert strat == {"use_savings", "reduce_discretionary", "move_date"}


# --- feedback recording (DB) ------------------------------------------------
async def _make_user(db: AsyncSession) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    db.add(user)
    await db.commit()
    return user.id


@pytest.mark.asyncio
async def test_record_feedback_accumulates_and_escalates(db_session: AsyncSession):
    uid = await _make_user(db_session)
    rid = "spending_reduction:reduce_food"
    for _ in range(2):
        await ps.record_feedback(db_session, uid, recommendation_id=rid,
                                 action=RecommendationAction.rejected, reason=RejectionReason.dislike_approach)
    row = await ps.get_policy(db_session, uid)
    assert row.policy["lever_stats"]["reduce_food"]["rejected"] == 2
    assert "reduce_food" in ps.policy_levers(row.policy)["soft"]   # 2 rejects -> soft

    count = await db_session.scalar(
        select(func.count()).select_from(RecommendationFeedback).where(RecommendationFeedback.user_id == uid)
    )
    assert count == 2


@pytest.mark.asyncio
async def test_emotional_flag_set_on_emotional_reject(db_session: AsyncSession):
    uid = await _make_user(db_session)
    await ps.record_feedback(db_session, uid, recommendation_id="timing_opportunity:move_date",
                             action=RecommendationAction.rejected, reason=RejectionReason.date_fixed,
                             reason_context="birthday with girlfriend", emotional_importance="high")
    row = await ps.get_policy(db_session, uid)
    assert row.policy["flags"]["protect_emotional_critical"] is True
    assert row.policy["provenance"]["move_date"]["reason_context"] == "birthday with girlfriend"
