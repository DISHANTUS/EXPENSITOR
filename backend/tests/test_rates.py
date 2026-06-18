"""Live exchange-rate refresh (open.er-api.com) — mocked fetch, no network."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.services import rates_service

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "rates@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_refresh_updates_rates_and_convert_uses_them(client: AsyncClient, monkeypatch):
    h = await _auth(client)

    # Seeded rate is stale (USD/INR 83.20 → 1000 INR ≈ $12.02).
    before = (await client.post("/api/v1/currency/convert",
              json={"amount": "1000", "from_currency": "INR", "to_currency": "USD"}, headers=h)).json()
    assert Decimal(str(before["converted_amount"])) > Decimal("11.5")

    # Live source now reports a realistic USD/INR ≈ 94.5.
    async def _fake():
        return {"USD": Decimal("1"), "INR": Decimal("94.5"), "JPY": Decimal("160"), "EUR": Decimal("0.92")}

    monkeypatch.setattr(rates_service, "_fetch_usd_rates", _fake)

    res = (await client.post("/api/v1/currency/refresh", params={"force": "true"}, headers=h)).json()
    assert res["updated"] >= 2 and res["source"] == "open.er-api.com" and res["stale"] is False

    after = (await client.post("/api/v1/currency/convert",
             json={"amount": "1000", "from_currency": "INR", "to_currency": "USD"}, headers=h)).json()
    # 1000 / 94.5 ≈ 10.58 — the realistic rate now drives conversions.
    assert Decimal("10.0") < Decimal(str(after["converted_amount"])) < Decimal("11.0")


async def test_rates_status_reports_source_and_date(client: AsyncClient, monkeypatch):
    h = await _auth(client, "rates2@example.com")

    async def _fake():
        return {"USD": Decimal("1"), "INR": Decimal("94.5")}

    monkeypatch.setattr(rates_service, "_fetch_usd_rates", _fake)
    await client.post("/api/v1/currency/refresh", params={"force": "true"}, headers=h)

    s = (await client.get("/api/v1/currency/rates-status", headers=h)).json()
    assert s["source"] == "open.er-api.com" and s["rate_date"] is not None and s["stale"] is False


async def test_refresh_failure_keeps_existing_rates(client: AsyncClient, monkeypatch):
    h = await _auth(client, "rates3@example.com")

    async def _boom():
        raise RuntimeError("provider down")

    monkeypatch.setattr(rates_service, "_fetch_usd_rates", _boom)
    res = (await client.post("/api/v1/currency/refresh", params={"force": "true"}, headers=h)).json()
    assert res["error"] == "fetch_failed"
    # Conversions still work off the seeded rates.
    conv = (await client.post("/api/v1/currency/convert",
            json={"amount": "100", "from_currency": "USD", "to_currency": "INR"}, headers=h)).json()
    assert Decimal(str(conv["converted_amount"])) > 0
