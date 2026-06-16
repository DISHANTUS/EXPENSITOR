"""Optional Ollama narrator (C5 Phase 3b) — rephrase-only, grounded, fallback-safe.

The deterministic Commentary stays the canonical source of truth. This package
may only restyle its wording: a generic narrator + an aggressive bidirectional
grounding guard + a deterministic prompt builder + a commentary adapter. All pure
and network-free; the I/O (HTTP to a local Ollama) lives in `ollama_service`.
"""

from __future__ import annotations

from app.intelligence.commentary.ollama import adapter, guard, narrator, prompt
from app.intelligence.commentary.ollama.guard import GroundingSpec, GuardResult, validate
from app.intelligence.commentary.ollama.narrator import NarrationRequest, NarrationResult, narrate

__all__ = [
    "adapter", "guard", "narrator", "prompt",
    "GroundingSpec", "GuardResult", "validate",
    "NarrationRequest", "NarrationResult", "narrate",
]
