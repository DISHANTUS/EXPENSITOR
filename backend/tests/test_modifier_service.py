"""Endpoint tests for the two-phase decision-modifier flow (C7a-2)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

QUOTE = "/api/v1/decisions/quote"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_phase1_asks_influence(client: AsyncClient):
    h = await _auth(client, "mod1@e.com")
    resp = await client.post(QUOTE, json={"item_label": "Order", "original_amount": "2000",
                                          "original_currency": "INR", "decision_kind": "custom"}, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(q["key"] == "involves" for q in body["pending_questions"])  # influence step first


async def test_phase2_free_delivery_finding(client: AsyncClient):
    h = await _auth(client, "mod2@e.com")
    resp = await client.post(QUOTE, json={
        "item_label": "Food order", "original_amount": "250", "original_currency": "INR", "decision_kind": "custom",
        "modifiers": {"involves": ["free_delivery"], "original_amount": "250", "delivery_fee": "60",
                      "free_delivery_threshold": "350", "final_amount": "350", "items_useful": "no"}}, headers=h)
    assert resp.status_code == 200, resp.text
    findings = {f["analyzer"]: f for f in resp.json()["modifier_findings"]}
    assert "free_delivery" in findings
    assert findings["free_delivery"]["facts"]["net"] == "40"
    # decision_change also fires (offer-type trigger present via free_delivery)
    assert "decision_change" in findings


async def test_subscription_finding_via_shape(client: AsyncClient):
    h = await _auth(client, "mod3@e.com")
    resp = await client.post(QUOTE, json={
        "item_label": "Streaming", "original_amount": "150", "original_currency": "INR",
        "decision_kind": "subscription", "outflow_shape": "recurring", "recurrence_months": 1,
        "modifiers": {"involves": ["subscription_pricing"], "subscription": {
            "alt_cadence": 12, "alt_price": "500", "expected_usage_months": 12}}}, headers=h)
    assert resp.status_code == 200, resp.text
    findings = {f["analyzer"] for f in resp.json()["modifier_findings"]}
    assert "subscription" in findings and "future_commitment" in findings
