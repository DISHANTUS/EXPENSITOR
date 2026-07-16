"""spending_shift follow-ups: the free_text response type, the one-time
"say more" re-ask when a reason is judged insufficient, and that it closes out
normally (Outcome + optional life-lesson) like every other advice kind once a
sufficient reason is given. Ollama is off in tests (conftest's autouse fixture),
so these all exercise the deterministic reason_judge path."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import User
from app.models.enums import AdviceKind, AdviceStatus
from app.services import advice_memory_service as ams

pytestmark = pytest.mark.asyncio


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def _uid(db_session, email: str):
    return await db_session.scalar(select(User.id).where(User.email == email))


async def test_http_response_actually_carries_response_type_and_needs_more_detail(
    client: AsyncClient, db_session
) -> None:
    """Regression guard: FastAPI's response_model silently DROPS any field the
    service returns but the Pydantic schema doesn't declare — a service-level
    test alone won't catch that, since it never goes through serialization.
    This hit both FollowUpQuestion.response_type and FollowUpAck.needs_more_detail
    live before the schemas were fixed to declare them."""
    h = await _auth(client, "shift_http@example.com")
    uid = await _uid(db_session, "shift_http@example.com")
    t = _today()

    row = await ams.record_advice(
        db_session, uid, kind=AdviceKind.spending_shift.value, subject_type="category",
        subject_label="Food & Dining", claim="Food & Dining spending has been running higher lately", today=t,
    )
    row.follow_up_due = t
    await db_session.commit()

    listed = (await client.get("/api/v1/advisor/follow-ups", headers=h)).json()
    assert listed[0]["response_type"] == "free_text"

    thin = (await client.post(f"/api/v1/advisor/follow-ups/{row.id}/answer", headers=h,
                              json={"answer": "explained", "detail": "idk"})).json()
    assert thin["needs_more_detail"] is True

    real = (await client.post(f"/api/v1/advisor/follow-ups/{row.id}/answer", headers=h,
                              json={"answer": "explained", "detail": "had a medical emergency this week"})).json()
    assert real["needs_more_detail"] is False
    assert real["circumstance"] == "medical"


async def test_spending_shift_is_a_free_text_question_not_choice_chips(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "shift1@example.com")
    uid = await _uid(db_session, "shift1@example.com")
    t = _today()

    row = await ams.record_advice(
        db_session, uid, kind=AdviceKind.spending_shift.value, subject_type="category",
        subject_label="Food & Dining", claim="Food & Dining spending has been running higher lately", today=t,
    )
    row.follow_up_due = t
    await db_session.commit()

    due = await ams.due_follow_ups(db_session, uid, today=t)
    assert len(due) == 1
    assert due[0]["response_type"] == "free_text"
    assert due[0]["question"].startswith("Food & Dining spending")


async def test_insufficient_reason_gets_one_gentle_reask_then_accepts(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "shift2@example.com")
    uid = await _uid(db_session, "shift2@example.com")
    t = _today()

    row = await ams.record_advice(
        db_session, uid, kind=AdviceKind.spending_shift.value, subject_type="category",
        subject_label="Food & Dining", claim="Food & Dining spending has been running higher lately", today=t,
    )

    # First attempt: a filler non-answer -> gentle re-ask, stays pending.
    result = await ams.answer(db_session, uid, row.id, answer="explained", detail="idk", today=t)
    assert result["needs_more_detail"] is True
    await db_session.refresh(row)
    assert row.status == AdviceStatus.pending.value
    assert row.follow_up_count == 1
    assert row.follow_up_due == t

    # Second attempt: still a filler answer, but the retry budget is spent ->
    # accepted anyway rather than nagging forever.
    result2 = await ams.answer(db_session, uid, row.id, answer="explained", detail="idk again", today=t)
    assert "needs_more_detail" not in result2 or result2.get("needs_more_detail") is not True
    await db_session.refresh(row)
    assert row.status == AdviceStatus.answered.value


async def test_sufficient_reason_closes_the_loop_immediately(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "shift3@example.com")
    uid = await _uid(db_session, "shift3@example.com")
    t = _today()

    row = await ams.record_advice(
        db_session, uid, kind=AdviceKind.spending_shift.value, subject_type="category",
        subject_label="Food & Dining", claim="Food & Dining spending has been running higher lately", today=t,
    )

    result = await ams.answer(
        db_session, uid, row.id, answer="explained",
        detail="had a medical emergency this week and ate out more", today=t,
    )
    assert result.get("needs_more_detail") is not True
    assert result["circumstance"] == "medical"
    await db_session.refresh(row)
    assert row.status == AdviceStatus.answered.value
    assert row.follow_up_count == 1  # never bounced through the re-ask branch


async def test_acknowledgment_copy_fits_an_explanation_not_a_yes_no_answer(client: AsyncClient, db_session) -> None:
    """Regression guard: 'explained' answers used to fall through to the
    generic ans=="no" copy ("it didn't happen this time") — nonsensical for a
    non-circumstance explanation like "friend visiting, ordered more takeout"."""
    h = await _auth(client, "shift4@example.com")
    uid = await _uid(db_session, "shift4@example.com")
    t = _today()

    row = await ams.record_advice(
        db_session, uid, kind=AdviceKind.spending_shift.value, subject_type="category",
        subject_label="Food & Dining", claim="Food & Dining spending has been running higher lately", today=t,
    )
    result = await ams.answer(
        db_session, uid, row.id, answer="explained",
        detail="had a friend visiting this week so we ordered a lot more takeout", today=t,
    )
    assert result["circumstance"] is None  # not a recognized E7 circumstance
    assert "didn’t happen" not in result["acknowledged"]
    assert "explaining" in result["acknowledged"].lower()
