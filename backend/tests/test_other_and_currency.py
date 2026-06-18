"""4a-3 tests: custom categories, reason interpreter, currency history."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_create_custom_category_is_idempotent(client: AsyncClient) -> None:
    h = await _auth(client, "cat-custom@example.com")
    r = await client.post("/api/v1/categories", json={"name": "Manga"}, headers=h)
    assert r.status_code == 201
    first_id = r.json()["id"]
    assert r.json()["is_system"] is False

    # Same name again -> reuse, not duplicate.
    again = await client.post("/api/v1/categories", json={"name": "Manga"}, headers=h)
    assert again.status_code == 201
    assert again.json()["id"] == first_id

    names = [c["name"] for c in (await client.get("/api/v1/categories", headers=h)).json()]
    assert names.count("Manga") == 1
    assert "Manga" in names  # appears in the picker now


async def test_reason_interpret_extracts_tags_and_label(client: AsyncClient) -> None:
    h = await _auth(client, "reason@example.com")
    r = await client.post(
        "/api/v1/reason/interpret",
        json={"text": "Bought train tickets for my Japan JLPT exam trip"},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["original"] == "Bought train tickets for my Japan JLPT exam trip"
    assert set(["japan", "jlpt", "travel", "education"]).issubset(set(body["tags"]))
    assert body["label"] == "JLPT"  # highest-priority tag
    assert body["confidence"] >= 0.9
    assert body["needs_more"] is False


async def test_reason_interpret_flags_vague(client: AsyncClient) -> None:
    h = await _auth(client, "reason2@example.com")
    r = (await client.post("/api/v1/reason/interpret", json={"text": "personal reason"}, headers=h)).json()
    assert r["needs_more"] is True
    assert r["original"] == "personal reason"  # never discarded


async def test_currency_history_records_change(client: AsyncClient) -> None:
    h = await _auth(client, "cur@example.com")
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC"}, headers=h)
    # Default base is INR; switch to JPY.
    r = await client.patch("/api/v1/users/me/settings", json={"base_currency": "JPY"}, headers=h)
    assert r.status_code == 200
    assert r.json()["base_currency"] == "JPY"
    hist = r.json()["currency_history"]
    assert hist is not None
    assert hist[-1]["currency"] == "JPY" and hist[-1].get("to") is None  # open period
    assert any(h.get("currency") == "INR" and h.get("to") is not None for h in hist)  # closed prior
