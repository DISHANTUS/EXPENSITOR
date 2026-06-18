"""4b-5b tests: companion intelligence — life lessons (confidence/lifecycle/forget/
restore/surfacing), reflection, success/achievements, prediction accuracy, recap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.intelligence.learning import accuracy as acc
from app.intelligence.learning import lessons as L
from app.intelligence.learning import reflection as R
from app.intelligence.learning import success as S
from app.models import User
from app.services import life_lesson_service as lls
from app.services import reflection_service

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/advisor/chat"
LESSONS = "/api/v1/advisor/lessons"
RECAP = "/api/v1/advisor/recap"
ACCURACY = "/api/v1/advisor/prediction-accuracy"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def _uid(db_session, email: str):
    return await db_session.scalar(select(User.id).where(User.email == email))


# --- pure intelligence --------------------------------------------------------
def test_lesson_confidence_grows_with_occurrences() -> None:
    assert L.confidence_for(1) == "low"
    assert L.confidence_for(2) == "medium"
    assert L.confidence_for(5) == "high"


def test_only_confirmed_lessons_are_surfaceable() -> None:
    assert not L.surfaceable("active", "low")        # one-off never volunteered
    assert L.surfaceable("confirmed", "medium")


def test_accuracy_band_and_by_type_summary() -> None:
    assert acc.band(100, 105, elapsed_months=2) == "accurate"
    assert acc.band(100, 125, elapsed_months=2) == "partial"
    assert acc.band(100, 200, elapsed_months=2) == "inaccurate"
    assert acc.band(100, 999, elapsed_months=0.5) == "pending"   # too early to judge
    summary = acc.summarize([
        {"band": "accurate", "forecast_type": "goal_eta"},
        {"band": "partial", "forecast_type": "goal_eta"},
        {"band": "inaccurate", "forecast_type": "life_event"},
    ])
    assert summary.accurate == 1 and summary.inaccurate == 1
    assert summary.by_type["goal_eta"]["accurate"] == 1
    assert summary.by_type["life_event"]["inaccurate"] == 1


def test_achievement_importance_excludes_non_achievements() -> None:
    ach = S.detect(completed_goals=[("Japan Fund", None)], streak_months=6,
                   first_salary=_today(), today=_today())
    types = {a.type for a in ach}
    assert S.GOAL_COMPLETED in types and S.FIRST_SALARY in types and S.SAVINGS_STREAK in types
    # A 2-month streak is NOT yet an achievement (avoids over-celebrating).
    assert not any(a.type == S.SAVINGS_STREAK for a in S.detect(streak_months=2, today=_today()))


def test_reflection_importance_gating() -> None:
    assert R.should_surface("goal_progress")        # high
    assert R.should_surface("food_improvement")     # medium
    assert not R.should_surface("red_day")          # low -> no fatigue


# --- life-lesson service ------------------------------------------------------
async def test_teach_grows_confidence_and_lifecycle(client: AsyncClient, db_session) -> None:
    await _auth(client, "lb1@example.com")
    uid = await _uid(db_session, "lb1@example.com")
    t = _today()
    a = await lls.teach(db_session, uid, source_text="my laptop broke, an unexpected expense", today=t)
    assert a.category == "emergency_fund" and a.confidence == "low" and a.status == "active"
    b = await lls.teach(db_session, uid, source_text="another surprise repair", today=t)
    assert b.id == a.id and b.occurrences == 2 and b.confidence == "medium" and b.status == "confirmed"


async def test_surfacing_is_confirmed_only(client: AsyncClient, db_session) -> None:
    await _auth(client, "lb2@example.com")
    uid = await _uid(db_session, "lb2@example.com")
    t = _today()
    await lls.teach(db_session, uid, source_text="my laptop broke", today=t)         # occ1 -> active
    assert await lls.relevant(db_session, uid, context="planning to buy a laptop", today=t) == []
    await lls.teach(db_session, uid, source_text="surprise medical bill", today=t)   # occ2 -> confirmed
    hits = await lls.relevant(db_session, uid, context="planning to buy a laptop", today=t)
    assert hits and hits[0].category == "emergency_fund"


async def test_forget_is_reversible(client: AsyncClient, db_session) -> None:
    await _auth(client, "lb3@example.com")
    uid = await _uid(db_session, "lb3@example.com")
    t = _today()
    row = await lls.teach(db_session, uid, source_text="my laptop broke", today=t)
    await lls.teach(db_session, uid, source_text="surprise repair", today=t)         # -> confirmed
    forgotten = await lls.forget(db_session, uid, row.id)
    assert forgotten["status"] == "forgotten"
    assert all(lr["id"] != str(row.id) for lr in await lls.list_(db_session, uid, today=t))   # hidden
    restored = await lls.restore(db_session, uid, row.id, today=t)
    assert restored["status"] == "confirmed"                                          # revived, not deleted


async def test_lifecycle_archives_stale_lessons(client: AsyncClient, db_session) -> None:
    await _auth(client, "lb4@example.com")
    uid = await _uid(db_session, "lb4@example.com")
    old = _today() - timedelta(days=600)
    await lls.teach(db_session, uid, source_text="my laptop broke", today=old)
    await lls.teach(db_session, uid, source_text="surprise repair", today=old)       # confirmed, last_observed old
    rows = await lls.list_(db_session, uid, today=_today())                           # triggers archive pass
    assert rows and rows[0]["status"] == "archived"                                   # kept, not deleted


async def test_times_helpful_increments(client: AsyncClient, db_session) -> None:
    await _auth(client, "lb5@example.com")
    uid = await _uid(db_session, "lb5@example.com")
    row = await lls.teach(db_session, uid, source_text="my laptop broke", today=_today())
    res = await lls.mark_helpful(db_session, uid, row.id)
    assert res["times_helpful"] == 1


async def test_reflection_answer_becomes_positive_lesson(client: AsyncClient, db_session) -> None:
    await _auth(client, "lb6@example.com")
    uid = await _uid(db_session, "lb6@example.com")
    res = await reflection_service.record_reflection(db_session, uid, trigger="goal_progress", answer="less_food")
    assert res["lesson"] is not None
    lessons = await lls.list_(db_session, uid)
    assert any(lr["category"] == "food" and lr["source"] == "reflection" for lr in lessons)


# --- API / chat ---------------------------------------------------------------
async def test_chat_teach_and_recall_lesson(client: AsyncClient) -> None:
    h = await _auth(client, "lb7@example.com")
    r = (await client.post(CHAT, json={"message": "remember that I overspent because my laptop broke"}, headers=h)).json()
    assert r["type"] == "answer" and "remember" in r["message"].lower()
    rows = (await client.get(LESSONS, headers=h)).json()
    assert rows and rows[0]["category"] == "emergency_fund"


async def test_chat_forget_lesson(client: AsyncClient) -> None:
    h = await _auth(client, "lb8@example.com")
    await client.post(CHAT, json={"message": "remember that my laptop broke unexpectedly"}, headers=h)
    r = (await client.post(CHAT, json={"message": "forget that laptop lesson"}, headers=h)).json()
    assert r["type"] == "answer" and "forgotten" in r["message"].lower()
    assert (await client.get(LESSONS, headers=h)).json() == []                        # hidden (still restorable)


async def test_chat_recap_is_structured(client: AsyncClient) -> None:
    h = await _auth(client, "lb9@example.com")
    target = (_today() + timedelta(days=400)).isoformat()
    await client.post("/api/v1/savings-goals",
                      json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                            "original_currency": "INR", "target_date": target}, headers=h)
    r = (await client.post(CHAT, json={"message": "what do you know about me?"}, headers=h)).json()
    assert r["type"] == "recap"
    assert r["recap"]["financial_identity"]["focus_areas"] == ["Japan Fund"]


async def test_recap_endpoint_structure(client: AsyncClient) -> None:
    h = await _auth(client, "lb10@example.com")
    recap = (await client.get(RECAP, headers=h)).json()
    assert "financial_identity" in recap and "lessons" in recap and "achievements" in recap


async def test_prediction_accuracy_pending_then_tracked(client: AsyncClient) -> None:
    h = await _auth(client, "lb11@example.com")
    # No forecasts yet -> honest "still learning".
    acc0 = (await client.get(ACCURACY, headers=h)).json()
    assert acc0["tracked"] == 0 and "learning" in acc0["note"].lower()
    # Make a forecast (records a snapshot); freshly made -> pending, not fabricated.
    await client.post("/api/v1/incomes", json={"source_type": "salary", "original_amount": "50000",
                                               "original_currency": "INR", "received_date": _today().isoformat()}, headers=h)
    await client.patch("/api/v1/users/me/settings", json={"starting_balance": "120000"}, headers=h)
    target = (_today() + timedelta(days=400)).isoformat()
    await client.post("/api/v1/savings-goals",
                      json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                            "original_currency": "INR", "target_date": target}, headers=h)
    await client.post(CHAT, json={"message": "when will I reach my goal?"}, headers=h)
    acc1 = (await client.get(ACCURACY, headers=h)).json()
    assert acc1["tracked"] == 1 and acc1["pending"] == 1
    assert "goal_eta" in acc1["by_type"]


async def test_lesson_surfaces_in_forecast_context(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "lb12@example.com")
    uid = await _uid(db_session, "lb12@example.com")
    # Confirm an emergency-fund lesson (taught twice).
    await lls.teach(db_session, uid, source_text="my laptop broke", today=_today())
    await lls.teach(db_session, uid, source_text="surprise medical bill", today=_today())
    # A life-event forecast about buying a laptop should surface that lesson.
    target = (_today() + timedelta(days=120)).isoformat()
    fc = (await client.post(CHAT, json={"message": "can I afford a 60000 laptop in October?"}, headers=h)).json()
    assert fc["type"] == "forecast"
    assert fc["forecast"]["surfaced_lesson"] and "taught me" in fc["forecast"]["surfaced_lesson"].lower()
