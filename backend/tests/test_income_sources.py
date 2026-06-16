"""Income-source endpoint tests (success + failure + ownership)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

URL = "/api/v1/income-sources"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _recurring(**overrides) -> dict:
    payload = {
        "label": "Salary",
        "source_type": "salary",
        "kind": "recurring",
        "original_amount": "50000",
        "original_currency": "INR",
        "recurrence_day": 1,
    }
    payload.update(overrides)
    return payload


def _one_time(**overrides) -> dict:
    payload = {
        "label": "Bonus",
        "source_type": "bonus",
        "kind": "one_time",
        "original_amount": "10000",
        "original_currency": "INR",
        "expected_date": "2026-12-20",
    }
    payload.update(overrides)
    return payload


async def test_create_recurring(client: AsyncClient):
    headers = await _auth(client, "is1@example.com")
    resp = await client.post(URL, headers=headers, json=_recurring())
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "recurring"
    assert body["recurrence_day"] == 1
    assert body["expected_date"] is None
    assert body["base_currency"] == "INR"
    assert Decimal(str(body["converted_amount"])) == Decimal("50000")  # INR->INR rate 1
    assert body["confidence_label"] == "Low"  # default reliability 0.5


async def test_create_recurring_requires_recurrence_day(client: AsyncClient):
    headers = await _auth(client, "is2@example.com")
    resp = await client.post(URL, headers=headers, json=_recurring(recurrence_day=None))
    assert resp.status_code == 422


async def test_create_one_time(client: AsyncClient):
    headers = await _auth(client, "is3@example.com")
    resp = await client.post(URL, headers=headers, json=_one_time())
    assert resp.status_code == 201
    body = resp.json()
    assert body["expected_date"] == "2026-12-20"
    assert body["recurrence_day"] is None


async def test_create_one_time_requires_expected_date(client: AsyncClient):
    headers = await _auth(client, "is4@example.com")
    resp = await client.post(URL, headers=headers, json=_one_time(expected_date=None))
    assert resp.status_code == 422


async def test_confidence_labels(client: AsyncClient):
    headers = await _auth(client, "is5@example.com")
    high = await client.post(URL, headers=headers, json=_recurring(reliability="0.9"))
    medium = await client.post(URL, headers=headers, json=_recurring(reliability="0.7"))
    low = await client.post(URL, headers=headers, json=_recurring(reliability="0.4"))
    assert high.json()["confidence_label"] == "High"
    assert medium.json()["confidence_label"] == "Medium"
    assert low.json()["confidence_label"] == "Low"


async def test_reliability_out_of_range(client: AsyncClient):
    headers = await _auth(client, "is6@example.com")
    resp = await client.post(URL, headers=headers, json=_recurring(reliability="1.5"))
    assert resp.status_code == 422


async def test_unsupported_currency(client: AsyncClient):
    headers = await _auth(client, "is7@example.com")
    resp = await client.post(URL, headers=headers, json=_recurring(original_currency="ZZZ"))
    assert resp.status_code == 422


async def test_negative_amount(client: AsyncClient):
    headers = await _auth(client, "is8@example.com")
    resp = await client.post(URL, headers=headers, json=_recurring(original_amount="-5"))
    assert resp.status_code == 422


async def test_foreign_currency_conversion(client: AsyncClient):
    headers = await _auth(client, "is9@example.com")
    resp = await client.post(
        URL, headers=headers, json=_recurring(original_currency="JPY", original_amount="100000")
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["base_currency"] == "INR"
    assert Decimal(str(body["exchange_rate"])) > 0
    assert Decimal(str(body["converted_amount"])) > 0


async def test_list_and_filter(client: AsyncClient):
    headers = await _auth(client, "is10@example.com")
    await client.post(URL, headers=headers, json=_recurring(is_active=True))
    await client.post(URL, headers=headers, json=_recurring(label="Paused", is_active=False))
    all_rows = (await client.get(URL, headers=headers)).json()
    assert len(all_rows) == 2
    active = (await client.get(URL + "?is_active=true", headers=headers)).json()
    assert len(active) == 1 and active[0]["is_active"] is True


async def test_ownership_isolation(client: AsyncClient):
    headers_a = await _auth(client, "owner_a@example.com")
    headers_b = await _auth(client, "owner_b@example.com")
    created = await client.post(URL, headers=headers_a, json=_recurring())
    source_id = created.json()["id"]
    # B cannot see or fetch A's source.
    assert (await client.get(URL, headers=headers_b)).json() == []
    assert (await client.get(f"{URL}/{source_id}", headers=headers_b)).status_code == 404


async def test_update_recomputes_fx(client: AsyncClient):
    headers = await _auth(client, "is11@example.com")
    created = (await client.post(URL, headers=headers, json=_recurring(original_amount="50000"))).json()
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"original_amount": "75000"})
    assert resp.status_code == 200
    assert Decimal(str(resp.json()["converted_amount"])) == Decimal("75000")


async def test_update_kind_consistency(client: AsyncClient):
    headers = await _auth(client, "is12@example.com")
    created = (await client.post(URL, headers=headers, json=_recurring())).json()
    # Switching to one_time without an expected_date must fail.
    resp = await client.patch(f"{URL}/{created['id']}", headers=headers, json={"kind": "one_time"})
    assert resp.status_code == 422


async def test_soft_delete(client: AsyncClient):
    headers = await _auth(client, "is13@example.com")
    created = (await client.post(URL, headers=headers, json=_recurring())).json()
    assert (await client.delete(f"{URL}/{created['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{URL}/{created['id']}", headers=headers)).status_code == 404
    assert (await client.get(URL, headers=headers)).json() == []


async def test_get_unknown_id(client: AsyncClient):
    headers = await _auth(client, "is14@example.com")
    resp = await client.get(f"{URL}/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


async def test_requires_auth(client: AsyncClient):
    assert (await client.get(URL)).status_code == 401
