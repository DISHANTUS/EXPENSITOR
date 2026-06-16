"""Expense endpoint tests (success + failure + filters + ownership)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

URL = "/api/v1/expenses"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _expense(**overrides) -> dict:
    payload = {
        "original_amount": "1200",
        "original_currency": "INR",
        "expense_date": "2026-06-10",
        "description": "Lunch",
    }
    payload.update(overrides)
    return payload


async def test_create_expense(client: AsyncClient):
    headers = await _auth(client, "exp1@example.com")
    resp = await client.post(URL, headers=headers, json=_expense())
    assert resp.status_code == 201
    body = resp.json()
    assert body["base_currency"] == "INR"
    assert Decimal(str(body["converted_amount"])) == Decimal("1200")
    assert body["category_id"] is None
    assert body["expense_date"] == "2026-06-10"


async def test_create_with_category(client: AsyncClient, system_category_id: str):
    headers = await _auth(client, "exp2@example.com")
    resp = await client.post(URL, headers=headers, json=_expense(category_id=system_category_id))
    assert resp.status_code == 201
    assert resp.json()["category_id"] == system_category_id


async def test_create_invalid_category(client: AsyncClient):
    headers = await _auth(client, "exp3@example.com")
    resp = await client.post(URL, headers=headers, json=_expense(category_id=str(uuid.uuid4())))
    assert resp.status_code == 422


async def test_create_unsupported_currency(client: AsyncClient):
    headers = await _auth(client, "exp4@example.com")
    resp = await client.post(URL, headers=headers, json=_expense(original_currency="ZZZ"))
    assert resp.status_code == 422


async def test_create_negative_amount(client: AsyncClient):
    headers = await _auth(client, "exp5@example.com")
    resp = await client.post(URL, headers=headers, json=_expense(original_amount="-5"))
    assert resp.status_code == 422


async def test_foreign_currency_conversion(client: AsyncClient):
    headers = await _auth(client, "exp6@example.com")
    resp = await client.post(
        URL, headers=headers, json=_expense(original_currency="JPY", original_amount="10000")
    )
    assert resp.status_code == 201
    assert Decimal(str(resp.json()["converted_amount"])) > 0


async def test_list_pagination(client: AsyncClient):
    headers = await _auth(client, "exp7@example.com")
    for i in range(3):
        await client.post(URL, headers=headers, json=_expense(original_amount=str(100 + i)))
    page = (await client.get(URL + "?limit=2&offset=0", headers=headers)).json()
    assert page["total"] == 3 and len(page["items"]) == 2


async def test_filter_by_category(client: AsyncClient, system_category_id: str):
    headers = await _auth(client, "exp8@example.com")
    await client.post(URL, headers=headers, json=_expense(category_id=system_category_id))
    await client.post(URL, headers=headers, json=_expense())  # uncategorized
    filtered = (await client.get(f"{URL}?category_id={system_category_id}", headers=headers)).json()
    assert filtered["total"] == 1


async def test_filter_by_date_range(client: AsyncClient):
    headers = await _auth(client, "exp9@example.com")
    await client.post(URL, headers=headers, json=_expense(expense_date="2026-06-01"))
    await client.post(URL, headers=headers, json=_expense(expense_date="2026-06-20"))
    resp = await client.get(f"{URL}?date_from=2026-06-10&date_to=2026-06-30", headers=headers)
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["expense_date"] == "2026-06-20"


async def test_get_ownership(client: AsyncClient):
    headers_a = await _auth(client, "exp_a@example.com")
    headers_b = await _auth(client, "exp_b@example.com")
    created = await client.post(URL, headers=headers_a, json=_expense())
    expense_id = created.json()["id"]
    assert (await client.get(f"{URL}/{expense_id}", headers=headers_b)).status_code == 404


async def test_update_recomputes_fx(client: AsyncClient):
    headers = await _auth(client, "exp10@example.com")
    created = (await client.post(URL, headers=headers, json=_expense(original_amount="1200"))).json()
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"original_amount": "1500"})
    assert resp.status_code == 200
    assert Decimal(str(resp.json()["converted_amount"])) == Decimal("1500")


async def test_soft_delete(client: AsyncClient):
    headers = await _auth(client, "exp11@example.com")
    created = (await client.post(URL, headers=headers, json=_expense())).json()
    assert (await client.delete(f"{URL}/{created['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{URL}/{created['id']}", headers=headers)).status_code == 404
    assert (await client.get(URL, headers=headers)).json()["total"] == 0


async def test_get_unknown_id(client: AsyncClient):
    headers = await _auth(client, "exp12@example.com")
    assert (await client.get(f"{URL}/{uuid.uuid4()}", headers=headers)).status_code == 404


async def test_requires_auth(client: AsyncClient):
    assert (await client.get(URL)).status_code == 401
