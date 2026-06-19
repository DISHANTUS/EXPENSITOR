"""LLM intent router (Stage 1 of the conversational upgrade).

The model is injected, so these tests stub it: they verify the DISPATCH (navigate /
answer / action / passthrough) and the all-important prod-safe fallback — on any
model failure or "passthrough", the deterministic ladder answers and nothing breaks.
Real-model JSON quality is validated separately against a live Ollama.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.intelligence.companion import llm_router
from app.services import ollama_service

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "brain@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _stub_model(monkeypatch, payload: str) -> None:
    """Turn the LLM brain on and make it return a fixed JSON payload."""
    async def fake_complete(messages):
        return payload
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(ollama_service, "complete", fake_complete)


async def _chat(client: AsyncClient, h: dict, message: str) -> dict:
    return (await client.post("/api/v1/advisor/chat", json={"message": message}, headers=h)).json()


# --- pure decision parsing ---------------------------------------------------

async def test_parse_strips_think_and_prose():
    d = llm_router.parse_decision('<think>reason</think> ok! {"kind":"navigate","route":"/timeline"}')
    assert d is not None and d.kind == "navigate" and d.route == "/timeline"


async def test_parse_rejects_unknown_route():
    assert llm_router.parse_decision('{"kind":"navigate","route":"/nope"}') is None


async def test_parse_rejects_garbage_and_empty_action():
    assert llm_router.parse_decision("totally not json") is None
    assert llm_router.parse_decision('{"kind":"action"}') is None  # no command


# --- dispatch (model stubbed) ------------------------------------------------

async def test_router_navigates(client: AsyncClient, monkeypatch):
    _stub_model(monkeypatch, '{"kind":"navigate","route":"/settings"}')
    h = await _auth(client)
    turn = await _chat(client, h, "could you take me to the settings screen please")
    assert turn["type"] == "help" and turn["route"] == "/settings"


async def test_router_answers_general_knowledge(client: AsyncClient, monkeypatch):
    _stub_model(monkeypatch, '{"kind":"answer","text":"A debit card spends money you already have; a credit card borrows it."}')
    h = await _auth(client, "gk@example.com")
    turn = await _chat(client, h, "whats the difference between a debit and a credit card")
    assert turn["type"] == "answer"
    assert "debit card spends" in (turn["message"] or "")


async def test_router_action_routes_to_preview(client: AsyncClient, monkeypatch):
    # the model normalises messy phrasing into a canonical command the parser handles
    _stub_model(monkeypatch, '{"kind":"action","command":"add 250 coffee expense"}')
    h = await _auth(client, "act@example.com")
    turn = await _chat(client, h, "ugh i blew like 250 on coffee again")
    assert "250" in (turn["message"] or "")
    assert turn["session"]["pending_action_text"] == "add 250 coffee expense"


async def test_router_passthrough_uses_deterministic_engines(client: AsyncClient, monkeypatch):
    _stub_model(monkeypatch, '{"kind":"passthrough"}')
    h = await _auth(client, "pt@example.com")
    turn = await _chat(client, h, "weekly report")
    assert turn["type"] in ("clarify", "report", "answer")   # engines answer, not the LLM
    assert turn["session"]["pending_action_text"] is None


async def test_router_model_failure_falls_back(client: AsyncClient, monkeypatch):
    async def boom(messages):
        raise RuntimeError("model unreachable")
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(ollama_service, "complete", boom)
    h = await _auth(client, "down@example.com")
    turn = await _chat(client, h, "weekly report")   # must not crash
    assert turn["type"] in ("clarify", "report", "answer")


async def test_brain_off_by_default_is_pure_deterministic(client: AsyncClient):
    # No stub: OLLAMA_ENABLED stays False (conftest) — same path production runs.
    h = await _auth(client, "off@example.com")
    turn = await _chat(client, h, "take me to settings")
    assert turn["type"] == "help" and turn["route"] == "/settings"   # deterministic nav still works
