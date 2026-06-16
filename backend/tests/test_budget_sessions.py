"""C3 Daily Budget Sessions tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import projection_service

pytestmark = pytest.mark.asyncio

URL = "/api/v1/budget-sessions"
EXP = "/api/v1/expenses"
TODAY = date.today().isoformat()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _uid(db_session: AsyncSession, email: str):
    return await db_session.scalar(select(User.id).where(User.email == email))


async def _expense(client: AsyncClient, headers, amount: str) -> str:
    resp = await client.post(EXP, headers=headers, json={"original_amount": amount, "original_currency": "INR", "expense_date": TODAY})
    return resp.json()["id"]


def _session(**o) -> dict:
    payload = {"title": "Weekend outing", "budget_amount": "1000", "currency": "INR"}
    payload.update(o)
    return payload


# --- CRUD -------------------------------------------------------------------

async def test_create_session(client: AsyncClient):
    h = await _auth(client, "bs1@e.com")
    r = await client.post(URL, headers=h, json=_session())
    assert r.status_code == 201
    b = r.json()
    assert b["status"] == "active"
    assert Decimal(str(b["converted_amount"])) == Decimal("1000")
    assert b["spent"] == "0.0000" or Decimal(str(b["spent"])) == Decimal("0")
    assert b["alerted_thresholds"] == []


async def test_list_active_returns_list(client: AsyncClient):
    h = await _auth(client, "bs2@e.com")
    await client.post(URL, headers=h, json=_session(title="A"))
    await client.post(URL, headers=h, json=_session(title="B"))
    active = (await client.get(f"{URL}/active", headers=h)).json()
    assert isinstance(active, list) and len(active) == 2  # multiple active sessions supported


async def test_unsupported_currency(client: AsyncClient):
    h = await _auth(client, "bs3@e.com")
    assert (await client.post(URL, headers=h, json=_session(currency="ZZZ"))).status_code == 422


# --- linking / utilization / warnings --------------------------------------

async def test_link_expense_updates_utilization(client: AsyncClient):
    h = await _auth(client, "bs4@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    eid = await _expense(client, h, "600")
    r = await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": eid})
    assert r.status_code == 200
    b = r.json()
    assert Decimal(str(b["spent"])) == Decimal("600")
    assert Decimal(str(b["remaining"])) == Decimal("400")
    assert Decimal(str(b["utilization_percent"])) == Decimal("60.00")
    assert b["expense_count"] == 1
    assert 50 in b["alerted_thresholds"]  # crossed 50%


async def test_warning_thresholds_dedup(client: AsyncClient):
    h = await _auth(client, "bs5@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": await _expense(client, h, "500")})  # 50%
    after = (await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": await _expense(client, h, "400")})).json()  # 90%
    assert set(after["alerted_thresholds"]) >= {50, 75, 90}
    feed = (await client.get("/api/v1/companion/feed?unread=true", headers=h)).json()
    assert any(i["type"] == "session_warning" for i in feed["items"])


async def test_cannot_double_link_expense(client: AsyncClient):
    h = await _auth(client, "bs6@e.com")
    s1 = (await client.post(URL, headers=h, json=_session())).json()["id"]
    s2 = (await client.post(URL, headers=h, json=_session())).json()["id"]
    eid = await _expense(client, h, "100")
    assert (await client.post(f"{URL}/{s1}/expenses", headers=h, json={"expense_id": eid})).status_code == 200
    assert (await client.post(f"{URL}/{s2}/expenses", headers=h, json={"expense_id": eid})).status_code == 422


async def test_unlink_expense(client: AsyncClient):
    h = await _auth(client, "bs7@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    eid = await _expense(client, h, "300")
    await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": eid})
    r = await client.delete(f"{URL}/{sid}/expenses/{eid}", headers=h)
    assert r.status_code == 200 and r.json()["expense_count"] == 0


# --- summary / lifecycle ----------------------------------------------------

async def test_complete_returns_summary(client: AsyncClient, system_category_id: str):
    h = await _auth(client, "bs8@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    resp = await client.post(EXP, headers=h, json={"original_amount": "250", "original_currency": "INR", "expense_date": TODAY, "category_id": system_category_id})
    await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": resp.json()["id"]})
    completed = (await client.post(f"{URL}/{sid}/complete", headers=h)).json()
    assert completed["status"] == "completed"
    assert Decimal(str(completed["saved"])) == Decimal("750")
    assert completed["expense_count"] == 1
    assert sum(Decimal(str(v)) for v in completed["category_breakdown"].values()) == Decimal("250")


async def test_complete_twice_rejected(client: AsyncClient):
    h = await _auth(client, "bs9@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    await client.post(f"{URL}/{sid}/complete", headers=h)
    assert (await client.post(f"{URL}/{sid}/complete", headers=h)).status_code == 422


async def test_soft_delete(client: AsyncClient):
    h = await _auth(client, "bs10@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    assert (await client.delete(f"{URL}/{sid}", headers=h)).status_code == 204
    assert (await client.get(f"{URL}/{sid}", headers=h)).status_code == 404


# --- ownership / auth -------------------------------------------------------

async def test_ownership(client: AsyncClient):
    ha = await _auth(client, "bs_a@e.com")
    hb = await _auth(client, "bs_b@e.com")
    sid = (await client.post(URL, headers=ha, json=_session())).json()["id"]
    assert (await client.get(f"{URL}/{sid}", headers=hb)).status_code == 404


async def test_requires_auth(client: AsyncClient):
    assert (await client.post(URL, json=_session())).status_code == 401


# --- projection / risk / guidance integration ------------------------------

async def test_projection_no_double_accounting(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "bsp1@e.com")
    sid = (await client.post(URL, headers=h, json=_session())).json()["id"]
    eid = await _expense(client, h, "400")
    uid = await _uid(db_session, "bsp1@e.com")
    before = (await projection_service.get_scenario(db_session, uid, today=date.today())).current_balance
    await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": eid})
    after = (await projection_service.get_scenario(db_session, uid, today=date.today())).current_balance
    assert before == after  # linking groups only; the expense was already counted


async def test_overrun_risk_and_guidance(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "bsp2@e.com")
    sid = (await client.post(URL, headers=h, json=_session(budget_amount="1000"))).json()["id"]
    await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": await _expense(client, h, "1200")})  # 120%
    uid = await _uid(db_session, "bsp2@e.com")
    risk = await projection_service.assess_risk(db_session, uid, today=date.today())
    assert "budget_session_overrun" in {s.code for s in risk.signals}
    guidance = await projection_service.compute_guidance(db_session, uid, today=date.today())
    assert any(a.action == "session_budget_exceeded" for a in guidance.recommended_actions)


async def test_slow_spending_guidance(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "bsp3@e.com")
    sid = (await client.post(URL, headers=h, json=_session(budget_amount="1000"))).json()["id"]
    await client.post(f"{URL}/{sid}/expenses", headers=h, json={"expense_id": await _expense(client, h, "800")})  # 80%
    uid = await _uid(db_session, "bsp3@e.com")
    guidance = await projection_service.compute_guidance(db_session, uid, today=date.today())
    assert any(a.action == "slow_spending" for a in guidance.recommended_actions)


async def test_session_started_companion_insight(client: AsyncClient):
    h = await _auth(client, "bsc1@e.com")
    await client.post(URL, headers=h, json=_session())
    feed = (await client.get("/api/v1/companion/feed", headers=h)).json()
    assert any(i["type"] == "session_started" for i in feed["items"])
