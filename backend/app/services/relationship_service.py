"""Relationship pages (Sprint 7) — each person's story, derived on read from the
data that already exists: their timeline (loans/events/gifts), trust profile
(receivable repayments), memories (advice recall + first/most-recent), and
upcoming plans. Deterministic; reuses the shared timeline collector + query.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.timeline import builder as B
from app.models import Person, Receivable
from app.models.enums import ReceivableKind, ReceivableStatus
from app.schemas.relationship import RelationshipDetail, RelationshipSummary, TrustProfile
from app.schemas.timeline import TimelineEntry
from app.services import (
    advice_memory_service,
    analytics_service,
    calendar_service,
    explain_service,
    settings_service,
    timeline_service,
)

_ZERO = Decimal("0")


async def _people_meta(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Person]:
    meta: dict[str, Person] = {}
    for p in (await db.execute(select(Person).where(Person.user_id == user_id))).scalars().all():
        meta[p.name.lower()] = p
        if p.nickname:
            meta[p.nickname.lower()] = p
    return meta


async def _trust(db: AsyncSession, user_id: uuid.UUID, name: str, currency: str) -> TrustProfile | None:
    recvs = (await db.execute(select(Receivable).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
        Receivable.source_name.ilike(name), Receivable.kind == ReceivableKind.one_time))).scalars().all()
    if not recvs:
        return None
    total = len(recvs)
    repaid = sum(1 for r in recvs if r.status == ReceivableStatus.received)
    outstanding_sum = sum((r.converted_amount for r in recvs if r.status == ReceivableStatus.pending), _ZERO)
    label = "Reliable" if repaid == total else ("Repaying" if repaid > 0 else "Owes you")
    outstanding = analytics_service._fmt(outstanding_sum, currency) if outstanding_sum > 0 else None  # noqa: SLF001
    return TrustProfile(label=label, repaid=repaid, total=total, outstanding=outstanding)


async def list_people(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> list[RelationshipSummary]:
    today = today or await calendar_service.user_today(db, user_id)
    entries, _people = await timeline_service.collect(db, user_id, today)
    meta = await _people_meta(db, user_id)

    by_person: dict[str, list[B.Entry]] = {}
    for e in entries:
        if e.person:
            by_person.setdefault(e.person, []).append(e)

    out: list[RelationshipSummary] = []
    for name, es in by_person.items():
        p = meta.get(name.lower())
        out.append(RelationshipSummary(
            name=name,
            relationship_type=(p.relationship_type.value if p and p.relationship_type else None),
            memory_count=len(es),
            future_count=sum(1 for e in es if e.when == B.FUTURE),
            reliability=(f"{p.reliability_score}" if p and p.reliability_score is not None else None),
        ))
    out.sort(key=lambda r: -r.memory_count)
    return out


async def detail(db: AsyncSession, user_id: uuid.UUID, name: str, *, today: date | None = None) -> RelationshipDetail:
    today = today or await calendar_service.user_today(db, user_id)
    currency = (await settings_service.get_settings(db, user_id)).base_currency
    entries, _ = await timeline_service.collect(db, user_id, today)

    low = name.lower()
    mine = B.prepare([e for e in entries
                      if (e.person or "").lower() == low or low in e.title.lower()], today=today)
    past = [e for e in mine if e.when != B.FUTURE]
    future = [e for e in mine if e.when == B.FUTURE]

    memories: list[str] = []
    if past:
        first = past[0]
        memories.append(f"First memory: {first.title}" + (f" ({first.date.isoformat()})" if first.date else ""))
        if len(past) > 1:
            last = past[-1]
            memories.append(f"Most recent: {last.title}" + (f" ({last.date.isoformat()})" if last.date else ""))
    recall = await advice_memory_service.recall(db, user_id, about=name, today=today)
    for item in recall.get("items", [])[:3]:
        memories.append(item["claim"])

    trust_note = ""
    try:
        ex = await explain_service.explain(db, user_id, ref=f"relationship:{name}")
        trust_note = ex.claim
    except Exception:  # noqa: BLE001 — a missing relationship explainer must not break the page
        trust_note = ""

    meta = await _people_meta(db, user_id)
    p = meta.get(low)
    return RelationshipDetail(
        name=name,
        relationship_type=(p.relationship_type.value if p and p.relationship_type else None),
        trust_note=trust_note,
        companion_note=f"{len(mine)} recorded memor{'y' if len(mine) == 1 else 'ies'} together.",
        timeline=[TimelineEntry.model_validate(e) for e in past],
        future=[TimelineEntry.model_validate(e) for e in future],
        memories=memories,
        trust=await _trust(db, user_id, name, currency),
    )
