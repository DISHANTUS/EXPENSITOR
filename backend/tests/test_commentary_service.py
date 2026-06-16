"""Endpoint/DB tests for the Commentary Layer (C5).

Phase 3a behaviour under the Phase 3b envelope: `deterministic_commentary` is the
canonical payload; with Ollama disabled (default) there is no narration.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

FUT = date.today() + timedelta(days=40)
FUT_MD = f"{FUT:%B} {FUT.day}"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _act(client, headers, text, **kw):
    return (await client.post("/api/v1/assistant/act", json={"text": text, **kw}, headers=headers)).json()


async def test_commentary_envelope_ollama_off(client: AsyncClient):
    h = await _auth(client, "c1@e.com")
    res = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()
    assert res["narration_status"] == "disabled" and res["narration_source"] == "deterministic"
    assert res["narrated_commentary"] is None
    assert res["grounding_version"] and res["commentary_schema_version"]
    det = res["deterministic_commentary"]
    assert isinstance(det["paragraphs"], list) and det["text"] and det["what_happened"]


async def test_cold_start_new_user_is_patient(client: AsyncClient):
    h = await _auth(client, "c2@e.com")
    det = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()["deterministic_commentary"]
    assert "don't have enough history yet" in (det["confidence_note"] or "")
    assert det["next_step"] is None
    assert len(det["paragraphs"]) <= 3                      # no advice spam (A9)


async def test_daily_brief_includes_commentary(client: AsyncClient):
    h = await _auth(client, "c3@e.com")
    brief = (await client.get("/api/v1/advisor/brief", headers=h)).json()
    assert brief["commentary"]["deterministic_commentary"]["paragraphs"]


async def test_assistant_result_includes_commentary(client: AsyncClient):
    h = await _auth(client, "c4@e.com")
    res = await _act(client, h, "add ₹250 lunch expense", confirm=True)
    assert res["type"] == "result" and "commentary" in res
    det = res["commentary"]["deterministic_commentary"]
    assert det["paragraphs"] and det["most_useful_number"] and "left to spend today" in det["most_useful_number"]


async def test_assistant_preview_includes_action_preview_commentary(client: AsyncClient):
    h = await _auth(client, "c5@e.com")
    res = await _act(client, h, "add ₹250 lunch expense")
    assert res["type"] == "preview" and "commentary" in res
    joined = " ".join(res["commentary"]["deterministic_commentary"]["paragraphs"])
    assert "stay the same" in joined or "stays the same" in joined   # A6 what-stays-the-same


async def test_commentary_surfaces_timing_when_known(client: AsyncClient):
    h = await _auth(client, "c6@e.com")
    await _act(client, h, f"Father will give ₹15,000 on {FUT_MD} evening", confirm=True)
    det = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()["deterministic_commentary"]
    assert det["timing_note"] and "₹15,000" in det["timing_note"] and "evening" in det["timing_note"]
