"""Chat → Action Layer: the text chat can DO things, not just answer.

A command runs through the same parse → clarify → preview → confirm → execute
pipeline the voice layer uses (assistant_service.act). Deterministic, no LLM —
the LLM router (later) only improves *understanding* on top of this.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "doer@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def _chat(client: AsyncClient, h: dict, message: str, session: dict | None = None) -> dict:
    body: dict = {"message": message}
    if session is not None:
        body["session"] = session
    return (await client.post("/api/v1/advisor/chat", json=body, headers=h)).json()


async def test_add_expense_preview_then_confirm_executes(client: AsyncClient):
    h = await _auth(client)
    # 1) command -> preview with a Yes/Cancel gateway and the command parked on the session
    preview = await _chat(client, h, "add 250 expense")
    assert "250" in (preview["message"] or "")
    assert "want me to do it" in (preview["message"] or "").lower()
    assert [o["label"] for o in preview["follow_ups"]] == ["Yes, do it", "Cancel"]
    assert preview["session"]["pending_action_text"] == "add 250 expense"

    # 2) "yes" (echoing the session) -> executes and clears the pending action
    done = await _chat(client, h, "yes", preview["session"])
    assert done["session"]["pending_action_text"] is None
    assert "250" in (done["message"] or "") or "added" in (done["message"] or "").lower()


async def test_cancel_does_not_execute(client: AsyncClient):
    h = await _auth(client, "canceler@example.com")
    preview = await _chat(client, h, "add 999 expense")
    done = await _chat(client, h, "no", preview["session"])
    assert done["session"]["pending_action_text"] is None
    assert "won't" in (done["message"] or "").lower() or "wont" in (done["message"] or "").lower()


async def test_missing_amount_asks_then_fills_then_previews(client: AsyncClient):
    h = await _auth(client, "slotfill@example.com")
    # no amount -> clarify, parking the command and the awaited slot on the session
    clar = await _chat(client, h, "add an expense")
    assert clar["type"] == "clarify"
    assert clar["session"]["pending_action_text"] == "add an expense"
    assert clar["session"]["pending_action_field"] == "amount"

    # answer the slot -> preview (slot filled, now awaiting confirm)
    preview = await _chat(client, h, "300", clar["session"])
    assert "300" in (preview["message"] or "")
    assert preview["session"]["pending_action_field"] is None
    assert preview["session"]["pending_action_text"] == "add an expense"


async def test_question_is_not_hijacked_as_an_action(client: AsyncClient):
    h = await _auth(client, "asker@example.com")
    turn = await _chat(client, h, "weekly report")
    # a query stays a query (no action parked); the report flow asks which week
    assert turn["session"]["pending_action_text"] is None
    assert turn["type"] in ("clarify", "report", "answer")


async def test_record_income_command_runs(client: AsyncClient):
    h = await _auth(client, "earner@example.com")
    # NOTE: the deterministic parser is phrasing-sensitive ("got/received" work,
    # "record … income" doesn't) — exactly the brittleness the LLM router will fix.
    preview = await _chat(client, h, "got 5000 income")
    assert "5000" in (preview["message"] or "").replace(",", "")  # may render as ₹5,000
    assert preview["session"]["pending_action_text"] == "got 5000 income"
    done = await _chat(client, h, "yes", preview["session"])
    assert done["session"]["pending_action_text"] is None
    assert "5000" in (done["message"] or "").replace(",", "") or "income" in (done["message"] or "").lower()
