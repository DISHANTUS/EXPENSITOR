"""4b-5a tests: the core learning loop — advice → follow-up → answer → Outcome →
recall, with importance gating and the honesty rule (no follow-up without advice;
E7 circumstance failures aren't lever failures)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AdviceMemory, Outcome, User
from app.services import advice_memory_service as ams

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/advisor/chat"
FOLLOWUPS = "/api/v1/advisor/follow-ups"
MEMORY = "/api/v1/advisor/memory"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str, *, starting: str = "0") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings",
                       json={"timezone": "UTC", "base_currency": "INR", "starting_balance": starting}, headers=h)
    return h


async def _uid(db_session, email: str):
    return await db_session.scalar(select(User.id).where(User.email == email))


# --- importance gating --------------------------------------------------------
async def test_importance_gating_high_vs_low(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "lr1@example.com")
    uid = await _uid(db_session, "lr1@example.com")
    t = _today()

    high = await ams.record_advice(db_session, uid, kind="forecast", subject_type="goal",
                                   subject_label="Japan Fund", claim="reach Japan Fund around March 2028", today=t)
    low = await ams.record_advice(db_session, uid, kind="recommendation", subject_type="single_expense",
                                  subject_label="coffee", claim="skip that coffee", today=t)
    assert high.importance == "high" and high.follow_up_due == t + timedelta(days=14)
    assert low.importance == "low" and low.follow_up_due is None        # never followed up

    # Nothing due yet (high is 14 days out, low never).
    assert await ams.due_follow_ups(db_session, uid, today=t) == []
    # 15 days later only the HIGH item is due.
    due = await ams.due_follow_ups(db_session, uid, today=t + timedelta(days=15))
    assert len(due) == 1 and due[0]["subject_label"] == "Japan Fund"
    assert [o["value"] for o in due[0]["options"]] == ["yes", "partial", "no"]


# --- answer -> Outcome -> recall ---------------------------------------------
async def test_answer_records_outcome_and_recall(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "lr2@example.com")
    uid = await _uid(db_session, "lr2@example.com")
    t = _today()
    advice = await ams.record_advice(db_session, uid, kind="recommendation", subject_type="category",
                                     subject_label="Food & Dining", lever_key="food",
                                     claim="reduce Food & Dining by 10%", today=t)
    later = t + timedelta(days=31)                                     # medium cadence = 30d
    due = await ams.due_follow_ups(db_session, uid, today=later)
    assert any(d["id"] == str(advice.id) for d in due)

    res = await ams.answer(db_session, uid, advice.id, answer="partial", detail="I tried but was busy", today=later)
    assert "partial" in res["acknowledged"].lower()
    # An Outcome (the evidence) was recorded.
    outcome = await db_session.scalar(select(Outcome).where(Outcome.user_id == uid))
    assert outcome is not None and outcome.outcome == "partial" and outcome.source == "user_reported"
    # The advice is closed and recallable with its answer.
    recall = await ams.recall(db_session, uid, about="food", today=later)
    assert recall["items"] and recall["items"][0]["answer"] == "partial"
    # Answered items no longer appear as due.
    assert not await ams.due_follow_ups(db_session, uid, today=later + timedelta(days=1))


async def test_circumstance_answer_is_e7_classified(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "lr3@example.com")
    uid = await _uid(db_session, "lr3@example.com")
    t = _today()
    advice = await ams.record_advice(db_session, uid, kind="recommendation", subject_type="category",
                                     subject_label="Shopping", lever_key="shopping",
                                     claim="reduce Shopping by 10%", today=t)
    res = await ams.answer(db_session, uid, advice.id, answer="no",
                           detail="my laptop broke — an unexpected expense", today=t + timedelta(days=31))
    assert res["circumstance"] == "unexpected_expense"               # E7: external, not a lever failure
    assert "one-off" in res["acknowledged"].lower() or "won’t count" in res["acknowledged"].lower()
    assert res["lesson_suggestion"]                                  # nudge toward an emergency buffer (4b-5b)


# --- honesty ------------------------------------------------------------------
async def test_no_followup_without_advice(client: AsyncClient) -> None:
    h = await _auth(client, "lr4@example.com")
    r = (await client.get(FOLLOWUPS, headers=h)).json()
    assert r == []                                                  # nothing fabricated


async def test_recall_empty_is_honest(client: AsyncClient) -> None:
    h = await _auth(client, "lr5@example.com")
    r = (await client.post(CHAT, json={"message": "what did you tell me about food?"}, headers=h)).json()
    assert r["type"] == "answer" and r["confidence"] == "insufficient"
    assert "don’t have anything" in r["message"].lower() or "haven’t given" in r["message"].lower()


# --- chat integration ---------------------------------------------------------
async def test_chat_relationship_advice_is_remembered(client: AsyncClient) -> None:
    h = await _auth(client, "lr6@example.com")
    past = (_today() - timedelta(days=5)).isoformat()
    await client.post("/api/v1/receivables",
                      json={"title": "Loan", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                            "original_amount": "5000", "original_currency": "INR", "expected_date": past}, headers=h)
    adv = (await client.post(CHAT, json={"message": "should I lend more to Ravi?"}, headers=h)).json()
    assert adv["type"] == "advisory"
    # The companion remembers it and can recall it later.
    rec = (await client.get(f"{MEMORY}?about=Ravi", headers=h)).json()
    assert rec["items"] and rec["items"][0]["kind"] == "relationship"


async def test_chat_forecast_is_remembered(client: AsyncClient) -> None:
    h = await _auth(client, "lr7@example.com", starting="120000")
    await client.post("/api/v1/incomes", json={"source_type": "salary", "original_amount": "50000",
                                               "original_currency": "INR", "received_date": _today().isoformat()}, headers=h)
    target = (_today() + timedelta(days=720)).isoformat()
    await client.post("/api/v1/savings-goals",
                      json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                            "original_currency": "INR", "target_date": target}, headers=h)
    fc = (await client.post(CHAT, json={"message": "when will I reach my goal?"}, headers=h)).json()
    assert fc["type"] == "forecast"
    rec = (await client.get(f"{MEMORY}?about=Japan", headers=h)).json()
    assert any(it["kind"] == "forecast" for it in rec["items"])


async def test_chat_checkin_surfaces_due_followup(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "lr8@example.com")
    uid = await _uid(db_session, "lr8@example.com")
    # Record advice 20 days "ago" so its 14-day follow-up is already due now.
    await ams.record_advice(db_session, uid, kind="forecast", subject_type="goal", subject_label="Japan Fund",
                            claim="reach Japan Fund around March 2028", today=_today() - timedelta(days=20))
    r = (await client.post(CHAT, json={"message": "anything to update?"}, headers=h)).json()
    assert r["type"] == "follow_up"
    assert r["follow_up"]["subject_label"] == "Japan Fund"
    assert [o["value"] for o in r["follow_up"]["options"]] == ["yes", "partial", "no"]


async def test_answer_endpoint_closes_loop(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "lr9@example.com")
    uid = await _uid(db_session, "lr9@example.com")
    advice = await ams.record_advice(db_session, uid, kind="forecast", subject_type="goal", subject_label="Japan Fund",
                                     claim="reach Japan Fund around March 2028", today=_today() - timedelta(days=20))
    due = (await client.get(FOLLOWUPS, headers=h)).json()
    assert due and due[0]["id"] == str(advice.id)
    ack = (await client.post(f"{FOLLOWUPS}/{advice.id}/answer", json={"answer": "yes"}, headers=h)).json()
    assert ack["outcome_id"]
    # No longer due once answered.
    assert (await client.get(FOLLOWUPS, headers=h)).json() == []
