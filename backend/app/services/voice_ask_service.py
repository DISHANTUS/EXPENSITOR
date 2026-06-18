"""Voice Conversation orchestration (Sprint 5c) — one entry the spoken client hits.

Routes a transcript to the right brain:
  * query  -> advisor_chat (5c-A): concise spoken reply + the structured turn.
  * command -> assistant.act (5c-B): the same parse→clarify→preview→confirm→execute
    pipeline, but spoken — missing slots and confirmations become questions the
    companion asks aloud, and the user's next utterance fills them.

Spoken answers are coerced back into typed values here (amount/date/category/
source) before handing to `act`. Deterministic; reuses chat/act/voice engines.
"""

from __future__ import annotations

import re
import uuid
import zlib
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.mood import voice as V
from app.intelligence.nlp import entities, parser as nlp
from app.intelligence.voice import voice_reply
from app.schemas.chat_primitives import ChatContext
from app.services import advisor_chat_service, assistant_service, calendar_service

_CONCERN_WORDS = ("over budget", "overdue", "behind", "not enough", "can’t", "cannot",
                  "won’t reach", "running low", "short")
# Spoken prompts (concise) for the slots voice asks about.
_PROMPT = {"amount": "How much?", "date": "For which date?", "source_name": "Who is it from?",
           "category": "What category was it?", "target_id": "Which one did you mean?"}
# act intent -> client reaction kind (5a.5 ack after a spoken write).
_REACTION_KIND = {nlp.ADD_EXPENSE: "expense", nlp.ADD_INCOME: "income", nlp.ADD_RECEIVABLE: "lent",
                  nlp.MARK_RECEIVABLE_RECEIVED: "loan_repaid", nlp.MOVE_EVENT: "event",
                  nlp.CREATE_SAVINGS_GOAL: "goal", nlp.CHANGE_SAVINGS_TARGET: "goal"}


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if p.strip()]


def _plan(speech: str, *, concern: bool = False) -> dict:
    ctx = V.VoiceContext(concern_count=1) if concern else V.VoiceContext()
    plan = V.build_voice_plan(ctx, salutation="", fact_segments=_sentences(speech),
                              signature=f"vr:{zlib.crc32(speech.encode('utf-8'))}")
    return V.as_dict(plan)


def _out(type_: str, speech: str, *, concern: bool = False, **extra) -> dict:
    return {"type": type_, "speech": speech, "voice": _plan(speech, concern=concern),
            "navigate": None, "turn": None, "session": ChatContext(), "awaiting": None,
            "command_text": None, "request_id": None, "action": None, "requires_confirmation": False,
            **extra}


def _name_match(v: str, cats: set[str]) -> str | None:
    low = v.lower().strip()
    return next((c for c in cats if low and (low in c.lower() or c.lower() in low)), None)


def _coerce(answers_raw: dict[str, Any] | None, cats: set[str], today: date) -> dict[str, Any]:
    """Turn raw spoken answers into typed values `act` understands."""
    out: dict[str, Any] = {}
    for field, val in (answers_raw or {}).items():
        v = str(val).strip()
        if not v:
            continue
        if field == "amount":
            amt, _ = entities.extract_amount(v)
            if amt is None:
                m = re.search(r"\d[\d,]*(?:\.\d+)?", v)
                amt = Decimal(m.group(0).replace(",", "")) if m else None
            if amt is not None:
                out["amount"] = amt
        elif field == "date":
            d = entities.extract_date(v, today)
            if d:
                out["date"] = d
        elif field == "category":
            c = entities.extract_category(v, cats) or _name_match(v, cats)
            if c:
                out["category"] = c
        elif field == "source_name":
            out["source_name"] = v.split()[0].capitalize()
        else:
            out[field] = v
    return out


def _wrap_act(res: dict, *, command: str, request_id: str, intent: str) -> dict:
    t = res.get("type")
    if t == "clarification":
        q = (res.get("questions") or [{}])[0]
        field = q.get("field")
        speech = q.get("prompt") or _PROMPT.get(field, "Could you clarify?")
        return _out("clarification", speech, awaiting=field, command_text=command, request_id=request_id)
    if t == "preview":
        return _out("preview", f"{res['summary']} Should I go ahead?", requires_confirmation=True,
                    command_text=command, request_id=request_id, action=intent)
    if t == "result":
        speech = (res.get("outcome") or {}).get("what_changed") or res.get("message") or "Done."
        return _out("result", speech, action=intent)
    if t == "advisory":  # buy decision quote — keep the spoken form short
        return _out("advisory", "Here’s my take — I’ve put the full breakdown on screen.")
    if t == "alternatives":
        return _out("alternatives", res.get("message") or "Here are some alternatives.")
    return _out(t or "unsupported", res.get("message") or "I couldn’t do that one.")


async def _write(db: AsyncSession, user_id: uuid.UUID, *, command: str, answers_raw: dict | None,
                 confirm: bool, request_id: str | None, today: date) -> dict:
    rid = request_id or uuid.uuid4().hex
    cats = await assistant_service._category_names(db, user_id)  # noqa: SLF001
    pr = nlp.parse(command, today=today, valid_category_names=cats)
    coerced = _coerce(answers_raw, cats, today)

    # Voice-only nicety: once we have an amount, ask an expense's category before
    # confirming (the "What category was it?" correction flow).
    if pr.intent == nlp.ADD_EXPENSE and not confirm:
        have_amount = pr.fields.get("amount") is not None or coerced.get("amount") is not None
        have_cat = pr.fields.get("category") is not None or "category" in coerced
        if have_amount and not have_cat:
            return _out("clarification", _PROMPT["category"], awaiting="category",
                        command_text=command, request_id=rid)

    res = await assistant_service.act(db, user_id, text=command, confirm=confirm, answers=coerced,
                                      request_id=rid, today=today)
    return _wrap_act(res, command=command, request_id=rid, intent=pr.intent)


def _concern(speech: str) -> bool:
    low = speech.lower()
    return any(w in low for w in _CONCERN_WORDS)


async def ask(db: AsyncSession, user_id: uuid.UUID, *, text: str, session: ChatContext | None = None,
              answers: dict | None = None, confirm: bool = False, request_id: str | None = None,
              command_text: str | None = None, today: date | None = None) -> dict:
    today = today or await calendar_service.user_today(db, user_id)
    command = (command_text or text).strip()

    pr = nlp.parse(command, today=today, valid_category_names=set())
    if pr.mutating or pr.intent == nlp.BUY_DECISION:
        return await _write(db, user_id, command=command, answers_raw=answers, confirm=confirm,
                            request_id=request_id, today=today)

    turn = await advisor_chat_service.chat(db, user_id, message=text, session=session)
    speech, navigate = voice_reply.summarize(turn)
    if "future me" in text.lower():        # "show me future me" → open the Future Me screen
        navigate = "future-me"
    out = _out(turn.type, speech, concern=_concern(speech), navigate=navigate)
    out["turn"], out["session"] = turn, turn.session
    return out
