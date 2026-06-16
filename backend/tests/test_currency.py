"""Currency service endpoint tests."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from httpx import AsyncClient


async def _auth(client: AsyncClient, email: str = "cur@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_list_currencies(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.get("/api/v1/currencies", headers=headers)
    assert resp.status_code == 200
    codes = {c["code"] for c in resp.json()}
    assert {"INR", "JPY", "USD", "EUR", "GBP", "CZK"} <= codes


async def test_get_currency(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.get("/api/v1/currencies/JPY", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "¥"
    assert body["decimal_digits"] == 0


async def test_get_currency_lowercase(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.get("/api/v1/currencies/jpy", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == "JPY"


async def test_get_currency_not_found(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.get("/api/v1/currencies/ZZZ", headers=headers)
    assert resp.status_code == 404


async def test_convert_same_currency(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/currency/convert",
        headers=headers,
        json={"amount": "100", "from_currency": "INR", "to_currency": "INR"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(str(body["exchange_rate"])) == Decimal("1")
    assert Decimal(str(body["converted_amount"])) == Decimal("100")


async def test_convert_cross_rate(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/currency/convert",
        headers=headers,
        json={"amount": "1000", "from_currency": "JPY", "to_currency": "INR"},
    )
    assert resp.status_code == 200
    body = resp.json()
    rate = Decimal(str(body["exchange_rate"]))
    converted = Decimal(str(body["converted_amount"]))
    # JPY->INR is a sensible sub-1 rate (~0.59 with seeded anchors).
    assert Decimal("0.4") < rate < Decimal("0.8")
    # Conversion is self-consistent with the returned rate, rounded to INR (2 dp).
    expected = (Decimal("1000") * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert converted == expected


async def test_convert_unsupported_currency(client: AsyncClient):
    headers = await _auth(client)
    resp = await client.post(
        "/api/v1/currency/convert",
        headers=headers,
        json={"amount": "100", "from_currency": "ZZZ", "to_currency": "INR"},
    )
    assert resp.status_code == 422


async def test_convert_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/currency/convert",
        json={"amount": "100", "from_currency": "JPY", "to_currency": "INR"},
    )
    assert resp.status_code == 401
