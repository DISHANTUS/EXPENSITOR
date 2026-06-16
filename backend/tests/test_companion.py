"""C1 Companion tests: events, guided help, engine insights, feed."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanionEvent

pytestmark = pytest.mark.asyncio

EVENTS = "/api/v1/companion/events"
FEED = "/api/v1/companion/feed"
TODAY = date.today()
FUTURE = (TODAY + timedelta(days=30)).isoformat()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# --- guided help ------------------------------------------------------------

async def test_page_open_returns_page_guidance(client: AsyncClient):
    h = await _auth(client, "cmp1@e.com")
    r = await client.post(EVENTS, headers=h, json={"event_type": "page_open", "surface": "converter"})
    assert r.status_code == 200
    msg = r.json()["messages"][0]
    assert msg["kind"] == "help" and msg["category"] == "page_guidance"
    assert "convert" in msg["message"].lower()
    assert msg["insight_id"] is None


async def test_button_click_returns_action_guidance(client: AsyncClient):
    h = await _auth(client, "cmp2@e.com")
    r = await client.post(EVENTS, headers=h, json={"event_type": "button_click", "surface": "expenses", "action": "add_expense"})
    assert r.status_code == 200
    assert r.json()["messages"][0]["category"] == "action_guidance"


async def test_unknown_surface_is_graceful(client: AsyncClient):
    h = await _auth(client, "cmp3@e.com")
    r = await client.post(EVENTS, headers=h, json={"event_type": "page_open", "surface": "totally_unknown_zzz"})
    assert r.status_code == 200
    assert r.json()["messages"]  # non-empty generic help


async def test_onboarding_step_guidance(client: AsyncClient):
    h = await _auth(client, "cmp4@e.com")
    r = await client.post(EVENTS, headers=h, json={"event_type": "onboarding_step", "action": "set_currency"})
    assert r.status_code == 200
    assert r.json()["messages"][0]["category"] == "page_guidance"


# --- engine-backed insights -------------------------------------------------

async def test_expense_completed_creates_insight_and_feeds(client: AsyncClient):
    h = await _auth(client, "cmp5@e.com")
    await client.post("/api/v1/expenses", headers=h, json={"original_amount": "500", "original_currency": "INR", "expense_date": TODAY.isoformat()})
    r = await client.post(EVENTS, headers=h, json={"event_type": "action_completed", "entity_type": "expense", "action": "created"})
    assert r.status_code == 200
    msg = r.json()["messages"][0]
    assert msg["kind"] == "insight" and msg["insight_id"] is not None
    assert msg["category"] in ("financial_insight", "warning")
    assert "safe_daily_spending" in msg["facts"]
    assert (await client.get(FEED, headers=h)).json()["total"] >= 1


async def test_planned_expense_completed_feasibility_insight(client: AsyncClient):
    h = await _auth(client, "cmp6@e.com")
    planned = (await client.post("/api/v1/planned-expenses", headers=h, json={"title": "Trip", "planned_date": FUTURE, "original_amount": "1000", "original_currency": "INR"})).json()
    r = await client.post(EVENTS, headers=h, json={"event_type": "action_completed", "entity_type": "planned_expense", "action": "created", "entity_id": planned["id"]})
    msg = r.json()["messages"][0]
    assert msg["type"] == "planned_feasibility"
    assert "verdict" in msg["facts"]


async def test_income_completed_insight(client: AsyncClient):
    h = await _auth(client, "cmp7@e.com")
    r = await client.post(EVENTS, headers=h, json={"event_type": "action_completed", "entity_type": "income", "action": "created"})
    assert r.json()["messages"][0]["kind"] == "insight"


async def test_settings_completed_insight(client: AsyncClient):
    h = await _auth(client, "cmp8@e.com")
    r = await client.post(EVENTS, headers=h, json={"event_type": "action_completed", "entity_type": "settings", "action": "updated"})
    assert r.json()["messages"][0]["type"] == "settings_updated"


# --- feed: pagination / unread / read --------------------------------------

async def test_feed_pagination_unread_and_mark_read(client: AsyncClient):
    h = await _auth(client, "cmp9@e.com")
    for _ in range(3):
        await client.post(EVENTS, headers=h, json={"event_type": "action_completed", "entity_type": "expense", "action": "created"})

    page = (await client.get(FEED + "?limit=2", headers=h)).json()
    assert page["total"] == 3 and len(page["items"]) == 2

    assert (await client.get(FEED + "/unread-count", headers=h)).json()["count"] == 3

    first_id = page["items"][0]["id"]
    marked = await client.patch(f"{FEED}/{first_id}/read", headers=h)
    assert marked.status_code == 200 and marked.json()["is_read"] is True

    assert (await client.get(FEED + "/unread-count", headers=h)).json()["count"] == 2
    assert (await client.get(FEED + "?unread=true", headers=h)).json()["total"] == 2


async def test_feed_ownership_isolation(client: AsyncClient):
    ha = await _auth(client, "cmp_a@e.com")
    hb = await _auth(client, "cmp_b@e.com")
    await client.post(EVENTS, headers=ha, json={"event_type": "action_completed", "entity_type": "expense", "action": "created"})
    insight_id = (await client.get(FEED, headers=ha)).json()["items"][0]["id"]
    assert (await client.patch(f"{FEED}/{insight_id}/read", headers=hb)).status_code == 404
    assert (await client.get(FEED, headers=hb)).json()["total"] == 0


# --- logging + auth ---------------------------------------------------------

async def test_every_event_is_logged(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "cmp_log@e.com")
    await client.post(EVENTS, headers=h, json={"event_type": "page_open", "surface": "converter"})
    count = await db_session.scalar(select(func.count()).select_from(CompanionEvent))
    assert count >= 1


async def test_requires_auth(client: AsyncClient):
    assert (await client.post(EVENTS, json={"event_type": "page_open", "surface": "converter"})).status_code == 401
