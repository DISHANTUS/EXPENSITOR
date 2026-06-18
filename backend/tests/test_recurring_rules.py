"""Recurring-rule CRUD tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "rr@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _today():
    return datetime.now(timezone.utc).date()


async def test_recurring_rule_crud(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post(
        "/api/v1/recurring-rules",
        json={"rule_type": "subscription", "label": "Netflix", "original_amount": "200",
              "original_currency": "inr", "recurrence_day": 15, "start_date": _today().isoformat(),
              "reason": "watching anime", "ai_metadata": {"why": "watching anime", "importance": "medium"}},
        headers=h,
    )
    assert r.status_code == 201
    body = r.json()
    rid = body["id"]
    assert body["original_currency"] == "INR"
    assert body["converted_amount"] == "200.0000"
    assert body["importance"] == "medium"
    assert body["reason"] == "watching anime"

    upd = await client.patch(f"/api/v1/recurring-rules/{rid}", json={"original_amount": "300"}, headers=h)
    assert upd.status_code == 200
    assert upd.json()["converted_amount"] == "300.0000"

    lst = (await client.get("/api/v1/recurring-rules", headers=h)).json()
    assert lst["total"] == 1

    assert (await client.delete(f"/api/v1/recurring-rules/{rid}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/recurring-rules", headers=h)).json()["total"] == 0


async def test_recurring_rule_rejects_bad_currency(client: AsyncClient) -> None:
    h = await _auth(client, "rr2@example.com")
    r = await client.post(
        "/api/v1/recurring-rules",
        json={"rule_type": "emi", "label": "Bike", "original_amount": "3500",
              "original_currency": "XYZ", "recurrence_day": 5, "start_date": _today().isoformat()},
        headers=h,
    )
    assert r.status_code == 422
