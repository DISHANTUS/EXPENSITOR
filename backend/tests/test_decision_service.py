"""DB-backed + endpoint tests for the Advisor brief and Decision quote (C7a)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSettings
from app.services import decision_service

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 6, 1)


async def _make_user(db: AsyncSession, *, starting: str) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    db.add(user)
    await db.flush()
    db.add(UserSettings(
        user_id=user.id, base_currency="INR", timezone="UTC",
        starting_balance=Decimal(starting), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ))
    await db.commit()
    return user.id


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_quote_service_end_to_end(db_session: AsyncSession):
    uid = await _make_user(db_session, starting="100000")
    out = await decision_service.quote(
        db_session, uid, item_label="Elden Ring", original_amount=Decimal("2000"),
        original_currency="INR", today=TODAY,
    )
    assert set(out) >= {"fx", "result", "explanation"}
    assert out["fx"]["converted_amount"] == "2000.00"
    assert out["result"]["verdict"] == "affordable"
    assert out["result"]["strategies"]  # at least one strategy
    assert out["explanation"]["headline"]


async def test_quote_endpoint(client: AsyncClient):
    headers = await _auth(client, "buyer@e.com")
    resp = await client.post(
        "/api/v1/decisions/quote",
        json={"item_label": "New phone", "original_amount": "30000", "original_currency": "INR",
              "decision_kind": "purchase", "constraints": {"willing_to_delay": True}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"]["verdict"] in ("affordable", "tight", "not_now")
    assert "impact" in body["result"] and "best_next_action" in body["explanation"]


async def test_quote_endpoint_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/decisions/quote",
        json={"item_label": "x", "original_amount": "100", "original_currency": "INR"},
    )
    assert resp.status_code == 401


async def test_advisor_brief_endpoint(client: AsyncClient):
    headers = await _auth(client, "brief@e.com")
    resp = await client.get("/api/v1/advisor/brief", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "context" in body and "explanations" in body
    assert "daily_remaining" in body["context"]
