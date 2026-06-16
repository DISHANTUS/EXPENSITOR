"""Endpoint/DB tests for the optional Ollama narrator (C5 Phase 3b).

No network: the model call (`ollama_service._generate`) is monkeypatched.
The centrepiece is the B10 invariant — the financial advice is byte-identical
with Ollama off and on; only the wording can differ.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services import ollama_service

pytestmark = pytest.mark.asyncio

FUT = date.today() + timedelta(days=40)
FUT_MD = f"{FUT:%B} {FUT.day}"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _act(client, headers, text, **kw):
    return (await client.post("/api/v1/assistant/act", json={"text": text, **kw}, headers=headers)).json()


def _echo():
    async def gen(messages):
        return messages[1]["content"].split("Text to rewrite:\n", 1)[1]
    return gen


def _hallucinate():
    async def gen(messages):
        return messages[1]["content"].split("Text to rewrite:\n", 1)[1] + " Save ₹9,999 more."
    return gen


async def _timeout(_messages):
    raise asyncio.TimeoutError


async def test_b10_advice_identical_only_wording_differs(client: AsyncClient, monkeypatch):
    h = await _auth(client, "ob1@e.com")
    await _act(client, h, "add ₹250 lunch expense", confirm=True)
    await _act(client, h, f"Father will give ₹15,000 on {FUT_MD} evening", confirm=True)

    off = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()
    assert off["narration_status"] == "disabled" and off["narrated_commentary"] is None

    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(ollama_service, "_generate", _echo())
    on = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()
    assert on["narration_status"] == "success" and on["narration_source"] == "ollama"
    assert on["narrated_commentary"]["text"] and on["narrated_commentary"]["source"] == "ollama"

    monkeypatch.setattr(ollama_service, "_generate", _hallucinate())
    hall = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()
    assert hall["narration_status"] == "validation_failed"
    assert hall["narrated_commentary"] is None and hall["narration_source"] == "deterministic"

    # The advice never changes — only the wording can (B10).
    assert off["deterministic_commentary"] == on["deterministic_commentary"] == hall["deterministic_commentary"]


async def test_timeout_falls_back_invisibly(client: AsyncClient, monkeypatch):
    h = await _auth(client, "ob2@e.com")
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(ollama_service, "_generate", _timeout)
    res = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()
    assert res["narration_status"] == "timeout" and res["narrated_commentary"] is None
    assert res["deterministic_commentary"]["paragraphs"]      # user still gets advice


async def test_assistant_result_narrated_when_enabled(client: AsyncClient, monkeypatch):
    h = await _auth(client, "ob4@e.com")
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(ollama_service, "_generate", _echo())
    res = await _act(client, h, "add ₹250 lunch expense", confirm=True)
    env = res["commentary"]
    assert env["narration_status"] == "success" and env["narrated_commentary"]["source"] == "ollama"
    assert env["deterministic_commentary"]["most_useful_number"]


async def test_observability_counters(client: AsyncClient, monkeypatch):
    h = await _auth(client, "ob3@e.com")
    ollama_service.reset_metrics()
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(ollama_service, "_generate", _echo())
    await client.get("/api/v1/commentary?surface=daily", headers=h)
    monkeypatch.setattr(ollama_service, "_generate", _hallucinate())
    await client.get("/api/v1/commentary?surface=daily", headers=h)
    m = ollama_service.metrics_snapshot()
    assert m["attempts"] >= 2 and m["success"] >= 1 and m["validation_failed"] >= 1 and m["fallback"] >= 1
