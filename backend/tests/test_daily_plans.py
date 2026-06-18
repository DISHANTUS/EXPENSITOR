"""Daily-plan budget tests: set, start-of-day lock, override, overspend reason."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "dp@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC"}, headers=h)
    return h


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def test_set_budget_then_locked_after_spending(client: AsyncClient) -> None:
    h = await _auth(client)
    today = _today()

    r = await client.put(f"/api/v1/daily-plans/{today}", json={"planned_budget": "1000"}, headers=h)
    assert r.status_code == 200
    assert r.json()["planned_budget"] == "1000.0000"

    r = await client.post(
        "/api/v1/expenses",
        json={"original_amount": "300", "original_currency": "INR", "expense_date": today},
        headers=h,
    )
    assert r.status_code == 201

    # Locked: changing the budget after spending began needs override.
    r = await client.put(f"/api/v1/daily-plans/{today}", json={"planned_budget": "1500"}, headers=h)
    assert r.status_code == 422
    assert "locked" in r.json()["detail"].lower()

    r = await client.put(
        f"/api/v1/daily-plans/{today}", json={"planned_budget": "1500", "override": True}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["modified_after_start"] is True


async def test_overspend_reason_is_stored(client: AsyncClient) -> None:
    h = await _auth(client, "dp2@example.com")
    today = _today()
    r = await client.put(f"/api/v1/daily-plans/{today}", json={"overspend_reason": "unplanned gadget"}, headers=h)
    assert r.status_code == 200
    assert r.json()["overspend_reason"] == "unplanned gadget"

    got = (await client.get(f"/api/v1/daily-plans/{today}", headers=h)).json()
    assert got["overspend_reason"] == "unplanned gadget"


async def test_past_budget_is_immutable(client: AsyncClient) -> None:
    h = await _auth(client, "dp3@example.com")
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    r = await client.put(f"/api/v1/daily-plans/{yesterday}", json={"planned_budget": "500"}, headers=h)
    assert r.status_code == 422
    assert "past" in r.json()["detail"].lower()


async def test_get_missing_plan_returns_null(client: AsyncClient) -> None:
    h = await _auth(client, "dp4@example.com")
    today = _today()
    r = await client.get(f"/api/v1/daily-plans/{today}", headers=h)
    assert r.status_code == 200
    assert r.json() is None
