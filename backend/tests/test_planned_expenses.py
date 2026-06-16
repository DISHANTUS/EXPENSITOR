"""Planned-expense endpoint tests (success + failure + filters + ownership)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

URL = "/api/v1/planned-expenses"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _planned(**overrides) -> dict:
    payload = {
        "title": "Birthday Gift",
        "planned_date": "2026-09-24",
        "original_amount": "1500",
        "original_currency": "INR",
    }
    payload.update(overrides)
    return payload


async def test_create_defaults(client: AsyncClient):
    headers = await _auth(client, "pe1@example.com")
    resp = await client.post(URL, headers=headers, json=_planned())
    assert resp.status_code == 201
    body = resp.json()
    assert body["priority"] == "medium"
    assert body["status"] == "planned"
    assert body["is_recurring"] is False
    assert Decimal(str(body["converted_amount"])) == Decimal("1500")


async def test_create_priority_critical(client: AsyncClient):
    headers = await _auth(client, "pe2@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(priority="critical"))
    assert resp.status_code == 201
    assert resp.json()["priority"] == "critical"


async def test_create_with_category(client: AsyncClient, system_category_id: str):
    headers = await _auth(client, "pe3@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(category_id=system_category_id))
    assert resp.status_code == 201
    assert resp.json()["category_id"] == system_category_id


async def test_create_invalid_category(client: AsyncClient):
    headers = await _auth(client, "pe4@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(category_id=str(uuid.uuid4())))
    assert resp.status_code == 422


async def test_create_missing_title(client: AsyncClient):
    headers = await _auth(client, "pe5@example.com")
    payload = _planned()
    del payload["title"]
    resp = await client.post(URL, headers=headers, json=payload)
    assert resp.status_code == 422


async def test_create_invalid_priority(client: AsyncClient):
    headers = await _auth(client, "pe6@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(priority="urgent"))
    assert resp.status_code == 422


async def test_create_unsupported_currency(client: AsyncClient):
    headers = await _auth(client, "pe7@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(original_currency="ZZZ"))
    assert resp.status_code == 422


async def test_create_negative_amount(client: AsyncClient):
    headers = await _auth(client, "pe8@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(original_amount="-1"))
    assert resp.status_code == 422


async def test_is_recurring_stored(client: AsyncClient):
    headers = await _auth(client, "pe9@example.com")
    resp = await client.post(URL, headers=headers, json=_planned(is_recurring=True))
    assert resp.status_code == 201
    assert resp.json()["is_recurring"] is True


async def test_list_pagination_and_status_filter(client: AsyncClient):
    headers = await _auth(client, "pe10@example.com")
    first = (await client.post(URL, headers=headers, json=_planned())).json()
    await client.post(URL, headers=headers, json=_planned(title="Concert"))
    await client.patch(f"{URL}/{first['id']}", headers=headers, json={"status": "completed"})
    planned_only = (await client.get(URL + "?status=planned", headers=headers)).json()
    assert planned_only["total"] == 1
    assert planned_only["items"][0]["status"] == "planned"


async def test_get_ownership(client: AsyncClient):
    headers_a = await _auth(client, "pe_a@example.com")
    headers_b = await _auth(client, "pe_b@example.com")
    created = await client.post(URL, headers=headers_a, json=_planned())
    planned_id = created.json()["id"]
    assert (await client.get(f"{URL}/{planned_id}", headers=headers_b)).status_code == 404


async def test_update_status_completed(client: AsyncClient):
    headers = await _auth(client, "pe11@example.com")
    created = (await client.post(URL, headers=headers, json=_planned())).json()
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_update_invalid_status(client: AsyncClient):
    headers = await _auth(client, "pe12@example.com")
    created = (await client.post(URL, headers=headers, json=_planned())).json()
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"status": "done"})
    assert resp.status_code == 422


async def test_update_recomputes_fx(client: AsyncClient):
    headers = await _auth(client, "pe13@example.com")
    created = (await client.post(URL, headers=headers, json=_planned(original_amount="1500"))).json()
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"original_amount": "2000"})
    assert resp.status_code == 200
    assert Decimal(str(resp.json()["converted_amount"])) == Decimal("2000")


async def test_soft_delete(client: AsyncClient):
    headers = await _auth(client, "pe14@example.com")
    created = (await client.post(URL, headers=headers, json=_planned())).json()
    assert (await client.delete(f"{URL}/{created['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{URL}/{created['id']}", headers=headers)).status_code == 404
    assert (await client.get(URL, headers=headers)).json()["total"] == 0


async def test_requires_auth(client: AsyncClient):
    assert (await client.get(URL)).status_code == 401
