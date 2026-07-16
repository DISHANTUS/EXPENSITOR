"""POST /planning/interpret over real HTTP.

Deliberately at the HTTP layer, not the service layer: FastAPI's response_model
silently DROPS any field the schema doesn't declare, and a service-level test
happily passes while the app receives nothing. That exact bug shipped twice on
this project (FollowUpAck.needs_more_detail, FollowUpQuestion.response_type).
"""

from __future__ import annotations

from httpx import AsyncClient

PLANNING = "/api/v1/planning/interpret"


async def _auth_headers(client: AsyncClient, email: str = "planning@example.com") -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123", "full_name": "P"},
    )
    tokens = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_interpret_returns_every_field_the_flow_needs(client: AsyncClient):
    headers = await _auth_headers(client)
    resp = await client.post(PLANNING, headers=headers, json={"text": "buy headphones for 3000 by december"})
    assert resp.status_code == 200
    body = resp.json()
    # Each of these must survive serialization — that's the whole point of
    # testing here rather than against the extractor directly.
    assert body["kind"] == "buy"
    assert body["item"] == "headphones"
    assert body["amount"] == 3000
    assert body["target_date"].endswith("-12-31")
    assert body["missing"] == []
    assert body["source"] == "rules"


async def test_a_vague_sentence_reports_what_is_still_missing(client: AsyncClient):
    headers = await _auth_headers(client, email="planning2@example.com")
    resp = await client.post(PLANNING, headers=headers, json={"text": "am planning to buy a new headphone"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "buy"
    assert body["amount"] is None
    assert set(body["missing"]) == {"amount", "target_date"}


async def test_interpret_requires_auth(client: AsyncClient):
    resp = await client.post(PLANNING, json={"text": "buy a bike"})
    assert resp.status_code == 401


async def test_empty_text_is_rejected(client: AsyncClient):
    headers = await _auth_headers(client, email="planning3@example.com")
    assert (await client.post(PLANNING, headers=headers, json={"text": ""})).status_code == 422


async def test_absurdly_long_text_is_rejected(client: AsyncClient):
    headers = await _auth_headers(client, email="planning4@example.com")
    resp = await client.post(PLANNING, headers=headers, json={"text": "buy " * 400})
    assert resp.status_code == 422


async def test_unknown_field_is_rejected(client: AsyncClient):
    headers = await _auth_headers(client, email="planning5@example.com")
    resp = await client.post(PLANNING, headers=headers, json={"text": "buy a bike", "kind": "save"})
    assert resp.status_code == 422
