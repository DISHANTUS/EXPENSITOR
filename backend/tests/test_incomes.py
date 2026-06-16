"""Actual-income endpoint tests (success + failure + pagination + ownership)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

URL = "/api/v1/incomes"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _income(**overrides) -> dict:
    payload = {
        "source_type": "salary",
        "original_amount": "80000",
        "original_currency": "INR",
        "received_date": "2026-06-01",
    }
    payload.update(overrides)
    return payload


async def test_create_income(client: AsyncClient):
    headers = await _auth(client, "inc1@example.com")
    resp = await client.post(URL, headers=headers, json=_income())
    assert resp.status_code == 201
    body = resp.json()
    assert body["base_currency"] == "INR"
    assert Decimal(str(body["converted_amount"])) == Decimal("80000")


async def test_create_income_foreign_currency(client: AsyncClient):
    headers = await _auth(client, "inc2@example.com")
    resp = await client.post(
        URL, headers=headers, json=_income(original_currency="JPY", original_amount="100000")
    )
    assert resp.status_code == 201
    body = resp.json()
    assert Decimal(str(body["exchange_rate"])) > 0
    assert Decimal(str(body["converted_amount"])) > 0


async def test_create_unsupported_currency(client: AsyncClient):
    headers = await _auth(client, "inc3@example.com")
    resp = await client.post(URL, headers=headers, json=_income(original_currency="ZZZ"))
    assert resp.status_code == 422


async def test_create_negative_amount(client: AsyncClient):
    headers = await _auth(client, "inc4@example.com")
    resp = await client.post(URL, headers=headers, json=_income(original_amount="-1"))
    assert resp.status_code == 422


async def test_list_pagination(client: AsyncClient):
    headers = await _auth(client, "inc5@example.com")
    for i in range(3):
        await client.post(URL, headers=headers, json=_income(original_amount=str(1000 + i)))
    page1 = (await client.get(URL + "?limit=2&offset=0", headers=headers)).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert page1["limit"] == 2 and page1["offset"] == 0
    page2 = (await client.get(URL + "?limit=2&offset=2", headers=headers)).json()
    assert len(page2["items"]) == 1


async def test_get_ownership(client: AsyncClient):
    headers_a = await _auth(client, "inc_a@example.com")
    headers_b = await _auth(client, "inc_b@example.com")
    created = await client.post(URL, headers=headers_a, json=_income())
    income_id = created.json()["id"]
    assert (await client.get(f"{URL}/{income_id}", headers=headers_b)).status_code == 404


async def test_update_recomputes_fx(client: AsyncClient):
    headers = await _auth(client, "inc6@example.com")
    created = (await client.post(URL, headers=headers, json=_income(original_amount="80000"))).json()
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"original_amount": "90000"})
    assert resp.status_code == 200
    assert Decimal(str(resp.json()["converted_amount"])) == Decimal("90000")


async def test_soft_delete(client: AsyncClient):
    headers = await _auth(client, "inc7@example.com")
    created = (await client.post(URL, headers=headers, json=_income())).json()
    assert (await client.delete(f"{URL}/{created['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{URL}/{created['id']}", headers=headers)).status_code == 404
    listing = (await client.get(URL, headers=headers)).json()
    assert listing["total"] == 0


async def test_get_unknown_id(client: AsyncClient):
    headers = await _auth(client, "inc8@example.com")
    resp = await client.get(f"{URL}/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_requires_auth(client: AsyncClient):
    assert (await client.get(URL)).status_code == 401
