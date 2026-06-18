"""Relationship-page schemas (Sprint 7) — a person's story, derived on read."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.timeline import TimelineEntry


class TrustProfile(BaseModel):
    label: str                 # Reliable | Repaying | Owes you
    repaid: int
    total: int
    outstanding: str | None = None


class RelationshipSummary(BaseModel):
    name: str
    relationship_type: str | None = None
    memory_count: int
    future_count: int = 0
    reliability: str | None = None


class RelationshipDetail(BaseModel):
    name: str
    relationship_type: str | None = None
    trust_note: str = ""
    companion_note: str = ""
    timeline: list[TimelineEntry] = []     # past + present
    future: list[TimelineEntry] = []       # upcoming plans
    memories: list[str] = []               # first / most-recent / recalled advice
    trust: TrustProfile | None = None


class RelationshipList(BaseModel):
    people: list[RelationshipSummary] = []
