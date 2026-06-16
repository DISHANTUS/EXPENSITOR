"""Deterministic NL parsing for the Action Layer (authoritative; no LLM)."""

from __future__ import annotations

from app.intelligence.nlp.parser import MUTATING, ParseResult, parse

__all__ = ["parse", "ParseResult", "MUTATING"]
