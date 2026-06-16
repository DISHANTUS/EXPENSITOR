"""C2 Receivables tests: CRUD, ownership, status, overdue, and engine/companion integration."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanionEvent, User
from app.models.enums import CompanionEntityType
from app.services import projection_service

pytestmark = pytest.mark.asyncio

URL = "/api/v1/receivables"
TODAY = date.today()
PAST = (TODAY - timedelta(days=5)).isoformat()
FUTURE = (TODAY + timedelta(days=10)).isoformat()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _uid(db_session: AsyncSession, email: str):
    return await db_session.scalar(select(User.id).where(User.email == email))


def _one_time(**overrides) -> dict:
    payload = {
        "title": "Loan to Rahul", "source_name": "Rahul", "source_type": "friend",
        "kind": "one_time", "original_amount": "5000", "original_currency": "INR", "expected_date": FUTURE,
    }
    payload.update(overrides)
    return payload


def _recurring(**overrides) -> dict:
    payload = {
        "title": "Father monthly", "source_name": "Father", "source_type": "family",
        "kind": "recurring", "original_amount": "10000", "original_currency": "INR", "recurrence_day": 10,
    }
    payload.update(overrides)
    return payload


# --- CRUD / validation ------------------------------------------------------

async def test_create_one_time(client: AsyncClient):
    h = await _auth(client, "rc1@e.com")
    resp = await client.post(URL, headers=h, json=_one_time())
    assert resp.status_code == 201
    b = resp.json()
    assert b["status"] == "pending" and b["source_name"] == "Rahul"
    assert Decimal(str(b["converted_amount"])) == Decimal("5000")
    assert b["next_expected_date"] is None  # only recurring


async def test_create_recurring_has_next_expected_date(client: AsyncClient):
    h = await _auth(client, "rc2@e.com")
    b = (await client.post(URL, headers=h, json=_recurring())).json()
    assert b["kind"] == "recurring" and b["recurrence_day"] == 10
    assert b["next_expected_date"] is not None and int(b["next_expected_date"][8:10]) == 10


async def test_one_time_requires_expected_date(client: AsyncClient):
    h = await _auth(client, "rc3@e.com")
    payload = _one_time()
    del payload["expected_date"]
    assert (await client.post(URL, headers=h, json=payload)).status_code == 422


async def test_recurring_requires_recurrence_day(client: AsyncClient):
    h = await _auth(client, "rc4@e.com")
    payload = _recurring()
    del payload["recurrence_day"]
    assert (await client.post(URL, headers=h, json=payload)).status_code == 422


async def test_source_name_required(client: AsyncClient):
    h = await _auth(client, "rc5@e.com")
    payload = _one_time()
    del payload["source_name"]
    assert (await client.post(URL, headers=h, json=payload)).status_code == 422


async def test_unsupported_currency(client: AsyncClient):
    h = await _auth(client, "rc6@e.com")
    assert (await client.post(URL, headers=h, json=_one_time(original_currency="ZZZ"))).status_code == 422


async def test_list_pagination(client: AsyncClient):
    h = await _auth(client, "rc7@e.com")
    for _ in range(3):
        await client.post(URL, headers=h, json=_one_time())
    page = (await client.get(URL + "?limit=2", headers=h)).json()
    assert page["total"] == 3 and len(page["items"]) == 2


async def test_ownership(client: AsyncClient):
    ha = await _auth(client, "rc_a@e.com")
    hb = await _auth(client, "rc_b@e.com")
    rid = (await client.post(URL, headers=ha, json=_one_time())).json()["id"]
    assert (await client.get(f"{URL}/{rid}", headers=hb)).status_code == 404
    assert (await client.patch(f"{URL}/{rid}", headers=hb, json={"title": "x"})).status_code == 404


# --- status / overdue -------------------------------------------------------

async def test_status_transition_received(client: AsyncClient):
    h = await _auth(client, "rc8@e.com")
    rid = (await client.post(URL, headers=h, json=_one_time())).json()["id"]
    resp = await client.patch(f"{URL}/{rid}", headers=h, json={"status": "received"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "received" and body["received_at"] is not None


async def test_patch_status_overdue_rejected(client: AsyncClient):
    h = await _auth(client, "rc9@e.com")
    rid = (await client.post(URL, headers=h, json=_one_time())).json()["id"]
    assert (await client.patch(f"{URL}/{rid}", headers=h, json={"status": "overdue"})).status_code == 422


async def test_overdue_detection(client: AsyncClient):
    h = await _auth(client, "rc10@e.com")
    rid = (await client.post(URL, headers=h, json=_one_time(expected_date=PAST))).json()["id"]
    body = (await client.get(f"{URL}/{rid}", headers=h)).json()
    assert body["status"] == "overdue" and body["days_overdue"] == 5


async def test_soft_delete(client: AsyncClient):
    h = await _auth(client, "rc11@e.com")
    rid = (await client.post(URL, headers=h, json=_one_time())).json()["id"]
    assert (await client.delete(f"{URL}/{rid}", headers=h)).status_code == 204
    assert (await client.get(f"{URL}/{rid}", headers=h)).status_code == 404
    assert (await client.get(URL, headers=h)).json()["total"] == 0


# --- projection / risk / guidance integration -------------------------------

async def test_projection_includes_future_receivable(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "rp1@e.com")
    rid = (await client.post(URL, headers=h, json=_one_time(expected_date=FUTURE, original_amount="3000"))).json()["id"]
    uid = await _uid(db_session, "rp1@e.com")
    scenario = await projection_service.get_scenario(db_session, uid, today=TODAY)
    assert rid in {str(e.source_id) for e in scenario.income_events}


async def test_overdue_receivable_risk_and_guidance(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "rp2@e.com")
    await client.post(URL, headers=h, json=_one_time(expected_date=PAST, original_amount="5000"))
    uid = await _uid(db_session, "rp2@e.com")

    risk = await projection_service.assess_risk(db_session, uid, today=TODAY)
    signal = next((s for s in risk.signals if s.code == "receivable_overdue"), None)
    assert signal is not None and signal.data["count"] == 1 and signal.data["max_days_overdue"] == 5

    guidance = await projection_service.compute_guidance(db_session, uid, today=TODAY)
    assert any(a.action == "follow_up_receivable" for a in guidance.recommended_actions)


async def test_recurring_never_overdue(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "rp3@e.com")
    await client.post(URL, headers=h, json=_recurring(recurrence_day=1))
    uid = await _uid(db_session, "rp3@e.com")
    risk = await projection_service.assess_risk(db_session, uid, today=TODAY)
    assert "receivable_overdue" not in {s.code for s in risk.signals}


# --- companion integration --------------------------------------------------

async def test_companion_event_and_insight_on_create(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "rcomp@e.com")
    await client.post(URL, headers=h, json=_one_time(expected_date=FUTURE))
    feed = (await client.get("/api/v1/companion/feed", headers=h)).json()
    assert feed["total"] >= 1
    insight = feed["items"][0]
    assert insight["type"].startswith("receivable_")
    assert insight["facts"]["source_name"] == "Rahul"
    count = await db_session.scalar(
        select(func.count()).select_from(CompanionEvent).where(CompanionEvent.entity_type == CompanionEntityType.receivable)
    )
    assert count >= 1


async def test_requires_auth(client: AsyncClient):
    assert (await client.post(URL, json=_one_time())).status_code == 401
