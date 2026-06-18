"""Fun-facts pipeline — the companion's *fallback* content.

Facts are drop-in `*.txt` files in a single folder (see ``app/data/facts``). Each
file is one category; the **filename** is the category. Inside a file every line
of the shape ``N. <fact>`` becomes one fact — and *only* those lines. Title
banners (``1000 FACTS ABOUT …`` — note the space, not a dot, after the number),
``====``/``----`` rules, section dividers (``--- ASIA ---``), ``END OF …``
footers and blank lines are ignored, so a serial number, heading or title can
never leak to the user.

Facts are educational filler. The companion shows them only when it has nothing
user-specific to say (see ``home_thought_service``), plus on demand from the orb
and the Home "Did you know?" card. Loaded once and cached; call :func:`reload`
to re-scan after dropping in new files.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.config import settings

# A fact line is "<number>. <text>". Anchored to the start, so a stray "1990."
# mid-sentence never matches, and banners like "1000 FACTS …" (space, no dot) and
# dividers ("--- ASIA ---") / footers ("END OF …") are skipped automatically.
_FACT_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")

# Filename tokens that are noise, not part of the category name.
_DROP_TOKENS = {"facts", "fact", "1000", "truly", "unique"}
_SMALL_WORDS = {"and", "of", "the", "a", "an", "in", "on", "to", "for"}

# A friendly emoji per known category (by slug). Unknown → the default bulb.
_EMOJI = {
    "money": "💰", "study": "🎓", "productivity": "🧠", "world": "🌍",
    "japan": "🇯🇵", "technology": "💻", "gaming": "🎮", "food": "🍜",
    "animal": "🦊", "animals": "🦊", "anime": "🎌", "movie": "🎬", "movies": "🎬",
    "vehicle": "🚗", "vehicles": "🚗", "weapons": "⚔️", "beauty-fashion": "💄",
    "love-and-romance": "❤️", "space": "🚀", "history": "📜", "science": "🔬",
}
_DEFAULT_EMOJI = "💡"


@dataclass(frozen=True)
class Fact:
    text: str
    category: str        # slug, e.g. "money"
    category_label: str  # display, e.g. "Money"
    emoji: str


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    emoji: str
    count: int


def parse_facts(text: str) -> list[str]:
    """Extract clean fact strings from raw file text — the single source of truth
    for what reaches the user. Only ``N. <fact>`` lines survive; the number is
    stripped and everything else (titles, rules, dividers, footers) is dropped."""
    out: list[str] = []
    for line in text.splitlines():
        m = _FACT_RE.match(line)
        if m:
            fact = m.group(1).strip()
            if fact:
                out.append(fact)
    return out


def _slug(stem: str) -> str:
    tokens = [t for t in re.split(r"[^a-z0-9]+", stem.lower()) if t and t not in _DROP_TOKENS]
    return "-".join(tokens) or "facts"


def _label(slug: str) -> str:
    # Title-case, but keep small joiners lowercase except as the first word.
    words = slug.split("-")
    return " ".join(w if (w in _SMALL_WORDS and i) else w.capitalize() for i, w in enumerate(words))


def _facts_dir() -> Path:
    if settings.FACTS_DIR:
        return Path(settings.FACTS_DIR)
    # app/services/facts_service.py → app/data/facts
    return Path(__file__).resolve().parent.parent / "data" / "facts"


# Cache: slug -> (label, [facts]). Built lazily from disk, refreshable via reload().
_cache: dict[str, tuple[str, list[str]]] | None = None


def _load() -> dict[str, tuple[str, list[str]]]:
    global _cache
    if _cache is not None:
        return _cache
    packs: dict[str, tuple[str, list[str]]] = {}
    directory = _facts_dir()
    if directory.is_dir():
        for path in sorted(directory.glob("*.txt")):
            try:
                raw = path.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                continue
            facts = parse_facts(raw)
            if not facts:
                continue
            slug = _slug(path.stem)
            if slug in packs:  # merge same-category files
                packs[slug][1].extend(facts)
            else:
                packs[slug] = (_label(slug), facts)
    _cache = packs
    return packs


def reload() -> None:
    """Drop the in-memory cache so the next call re-scans the folder."""
    global _cache
    _cache = None


def categories() -> list[Category]:
    return [
        Category(key=slug, label=label, emoji=_EMOJI.get(slug, _DEFAULT_EMOJI), count=len(facts))
        for slug, (label, facts) in sorted(_load().items())
    ]


def pack(key: str) -> list[str]:
    """All facts in one category — used by the client to cache a pack for offline."""
    entry = _load().get(key)
    return list(entry[1]) if entry else []


def _pool(keys: list[str] | None) -> list[tuple[str, str, str]]:
    """Flatten (text, slug, label) across the requested categories (or all)."""
    data = _load()
    chosen = [k for k in (keys or []) if k in data] or list(data.keys())
    pool: list[tuple[str, str, str]] = []
    for slug in chosen:
        label, facts = data[slug]
        pool.extend((f, slug, label) for f in facts)
    return pool


def _fact_from(text: str, slug: str, label: str) -> Fact:
    return Fact(text=text, category=slug, category_label=label, emoji=_EMOJI.get(slug, _DEFAULT_EMOJI))


def random_fact(categories: list[str] | None = None) -> Fact | None:
    """A fresh random fact — for the orb's single-tap ('tap again for another')."""
    pool = _pool(categories)
    if not pool:
        return None
    return _fact_from(*random.choice(pool))


def daily_fact(day: date, categories: list[str] | None = None) -> Fact | None:
    """A *deterministic* fact for a given day — stable for the Home card so it
    doesn't reshuffle on every refresh, but rotates once per day."""
    pool = _pool(categories)
    if not pool:
        return None
    digest = hashlib.sha256(day.isoformat().encode()).hexdigest()
    idx = int(digest, 16) % len(pool)
    return _fact_from(*pool[idx])


def fallback_thought(day: date, categories: list[str] | None = None) -> str | None:
    """A 'Did you know?' line for the companion thought — used **only** when there
    is no user-specific insight to show. Seeded off the day + a salt so it differs
    from the Home card's daily fact. Returns None when no facts are available."""
    pool = _pool(categories)
    if not pool:
        return None
    digest = hashlib.sha256(f"thought:{day.isoformat()}".encode()).hexdigest()
    text, _slug_, _label_ = pool[int(digest, 16) % len(pool)]
    return f"Did you know? {text}"
