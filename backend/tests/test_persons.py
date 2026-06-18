"""Person (relationship memory) CRUD + receivable linkage tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "person@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_person_crud(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post(
        "/api/v1/persons",
        json={"name": "Ravi", "relationship_type": "friend", "tags": ["college"],
              "ai_metadata": {"why": "close friend", "importance": "high"}},
        headers=h,
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["relationship_type"] == "friend"
    assert r.json()["tags"] == ["college"]
    assert r.json()["ai_metadata"]["why"] == "close friend"

    upd = await client.patch(f"/api/v1/persons/{pid}", json={"nickname": "Rav", "reliability_score": "0.4"}, headers=h)
    assert upd.status_code == 200
    assert upd.json()["nickname"] == "Rav"

    lst = (await client.get("/api/v1/persons", headers=h)).json()
    assert lst["total"] == 1

    assert (await client.delete(f"/api/v1/persons/{pid}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/persons", headers=h)).json()["total"] == 0


async def test_receivable_links_person(client: AsyncClient) -> None:
    h = await _auth(client, "person2@example.com")
    pid = (await client.post(
        "/api/v1/persons", json={"name": "Arun", "relationship_type": "friend"}, headers=h
    )).json()["id"]

    future = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
    r = await client.post(
        "/api/v1/receivables",
        json={"title": "Lunch loan", "source_name": "Arun", "source_type": "friend", "kind": "one_time",
              "original_amount": "3000", "original_currency": "INR", "expected_date": future, "person_id": pid},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["person_id"] == pid


async def test_invalid_person_rejected_on_receivable(client: AsyncClient) -> None:
    h = await _auth(client, "person3@example.com")
    future = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
    r = await client.post(
        "/api/v1/receivables",
        json={"title": "x", "source_name": "y", "source_type": "friend", "kind": "one_time",
              "original_amount": "100", "original_currency": "INR", "expected_date": future,
              "person_id": "00000000-0000-4000-a000-0000000000ff"},
        headers=h,
    )
    assert r.status_code == 422
