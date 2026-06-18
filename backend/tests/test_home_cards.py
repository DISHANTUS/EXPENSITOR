"""Home Living Quick Cards (UI-X) — Story/Future/People/Focus previews."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "cards@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_default_cards_for_empty_account(client: AsyncClient):
    h = await _auth(client)
    body = (await client.get("/api/v1/companion/home-cards", headers=h)).json()
    keys = [c["key"] for c in body["cards"]]
    # Story, Future and Focus always show (with get-started defaults); People only
    # appears once there's someone to show, so a thin account omits it.
    assert "story" in keys and "future" in keys and "focus" in keys
    assert "people" not in keys
    by_key = {c["key"]: c for c in body["cards"]}
    assert by_key["story"]["route"] == "/timeline"
    assert by_key["future"]["route"] == "/future-me"
    assert by_key["focus"]["route"] == "/plan-today"


async def test_cards_preview_real_life(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "monthly_target",
        "original_amount": "2000", "original_currency": "INR"}, headers=h)
    # A loan to a friend → a tracked person + an upcoming repayment milestone.
    await client.post("/api/v1/receivables", json={
        "title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
        "original_amount": "3000", "original_currency": "INR", "expected_date": "2026-12-10"}, headers=h)

    body = (await client.get("/api/v1/companion/home-cards", headers=h)).json()
    by_key = {c["key"]: c for c in body["cards"]}

    # People card now surfaces, headlined by the person.
    assert "people" in by_key
    assert by_key["people"]["headline"] == "Ravi"
    assert by_key["people"]["route"] == "/relationships"

    # Story card reflects a real memory (lending to Ravi is a past entry).
    assert by_key["story"]["subtitle"]
