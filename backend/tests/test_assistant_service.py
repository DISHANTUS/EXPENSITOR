"""Endpoint tests for the Natural-Language Action Layer (Phase 2)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, User

pytestmark = pytest.mark.asyncio

ACT = "/api/v1/assistant/act"
FUT = date.today() + timedelta(days=40)
FUT2 = date.today() + timedelta(days=55)
FUT_MD = f"{FUT:%B} {FUT.day}"
FUT2_MD = f"{FUT2:%B} {FUT2.day}"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _act(client, headers, text, **kw):
    return (await client.post(ACT, json={"text": text, **kw}, headers=headers)).json()


# --- core flows -------------------------------------------------------------
async def test_add_expense_preview_then_confirm(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "nl1@e.com")
    preview = await _act(client, h, "add ₹250 lunch expense")
    assert preview["type"] == "preview" and "250" in preview["summary"]

    result = await _act(client, h, "add ₹250 lunch expense", confirm=True)
    assert result["type"] == "result" and result["outcome"]["verified"] is True
    o = result["outcome"]
    assert o["what_changed"] and o["most_useful_number"] and "daily_budget" in o
    uid = await db_session.scalar(select(User.id).where(User.email == "nl1@e.com"))
    count = await db_session.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == uid))
    assert count == 1


async def test_clarification_when_amount_missing(client: AsyncClient):
    h = await _auth(client, "nl2@e.com")
    res = await _act(client, h, "add a lunch expense")
    assert res["type"] == "clarification" and any(q["field"] == "amount" for q in res["questions"])


async def test_unsupported_is_graceful(client: AsyncClient):
    h = await _auth(client, "nl3@e.com")
    assert (await _act(client, h, "tell me a joke"))["type"] == "unsupported"


async def test_add_receivable_with_timing(client: AsyncClient):
    h = await _auth(client, "nl4@e.com")
    res = await _act(client, h, f"Father will give ₹15,000 on {FUT_MD} evening", confirm=True)
    assert res["type"] == "result"
    assert res["outcome"]["next_income"] and "15,000" in res["outcome"]["next_income"]
    recs = (await client.get("/api/v1/receivables", headers=h)).json()["items"]
    assert recs and recs[0]["expected_time_window"] == "evening"


async def test_move_event_without_date_suggests(client: AsyncClient):
    h = await _auth(client, "nl5@e.com")
    await client.post("/api/v1/planned-expenses", json={
        "title": "Outing", "planned_date": (date.today() + timedelta(days=30)).isoformat(),
        "original_amount": "1500", "original_currency": "INR", "occasion_type": "outing"}, headers=h)
    res = await _act(client, h, "move the outing")
    assert res["type"] == "clarification" and any(q["field"] == "date" for q in res["questions"])

    moved = await _act(client, h, f"move outing to {FUT2_MD}", confirm=True)
    assert moved["type"] == "result"
    items = (await client.get("/api/v1/planned-expenses", headers=h)).json()["items"]
    assert items[0]["planned_date"] == FUT2.isoformat()


async def test_mark_receivable_received(client: AsyncClient):
    h = await _auth(client, "nl6@e.com")
    await client.post("/api/v1/receivables", json={
        "title": "Loan", "source_name": "Rahul", "source_type": "friend", "kind": "one_time",
        "original_amount": "5000", "original_currency": "INR", "expected_date": FUT.isoformat()}, headers=h)
    res = await _act(client, h, "mark Rahul's receivable as received", confirm=True)
    assert res["type"] == "result"
    rec = (await client.get("/api/v1/receivables", headers=h)).json()["items"][0]
    assert rec["status"] == "received"


async def test_buy_decision_asks_modifier_info(client: AsyncClient):
    h = await _auth(client, "nl7@e.com")
    res = await _act(client, h, "I want to buy a phone for ₹30,000")
    # D16: gather modifier info (influence step) before the quote
    assert res["type"] in ("clarification", "advisory")
    if res["type"] == "clarification":
        assert any(q.get("key") == "involves" or q.get("field") for q in res["questions"])


async def test_create_savings_goal(client: AsyncClient):
    h = await _auth(client, "nl8@e.com")
    res = await _act(client, h, "I want to save ₹50,000 this month", confirm=True)
    assert res["type"] == "result"
    goals = (await client.get("/api/v1/savings-goals", headers=h)).json()["items"]
    assert goals and goals[0]["kind"] == "monthly_target" and goals[0]["original_amount"] == "50000.0000"


async def test_change_savings_target(client: AsyncClient):
    h = await _auth(client, "nl9@e.com")
    await client.post("/api/v1/savings-goals", json={
        "name": "Phone", "kind": "custom_goal", "original_amount": "85000", "original_currency": "INR",
        "target_date": FUT.isoformat()}, headers=h)
    res = await _act(client, h, "change my phone savings target to ₹40,000", confirm=True)
    assert res["type"] == "result"
    goals = (await client.get("/api/v1/savings-goals", headers=h)).json()["items"]
    assert goals[0]["original_amount"] == "40000.0000"


async def test_reject_switches_to_alternatives(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "nl10@e.com")
    # seed spending so alternatives exist
    uid = await db_session.scalar(select(User.id).where(User.email == "nl10@e.com"))
    food = await db_session.scalar(select(Category.id).where(Category.name == "Food & Dining", Category.is_system.is_(True)))
    d = date.today() - timedelta(days=70)
    from decimal import Decimal
    while d <= date.today():
        db_session.add(Expense(user_id=uid, category_id=food, original_amount=Decimal("200" if d.weekday() >= 5 else "100"),
                               original_currency="INR", exchange_rate=Decimal("1"), converted_amount=Decimal("200" if d.weekday() >= 5 else "100"),
                               base_currency="INR", expense_date=d))
        d += timedelta(days=1)
    await db_session.commit()
    res = await _act(client, h, "I can't move the outing")
    assert res["type"] == "alternatives" and isinstance(res["recommendations"], list)


async def test_idempotent_confirm(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "nl11@e.com")
    await _act(client, h, "add ₹100 expense", confirm=True, request_id="req-1")
    second = await _act(client, h, "add ₹100 expense", confirm=True, request_id="req-1")
    assert second.get("idempotent_replay") is True
    uid = await db_session.scalar(select(User.id).where(User.email == "nl11@e.com"))
    count = await db_session.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == uid))
    assert count == 1  # second confirm did not duplicate
