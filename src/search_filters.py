"""
Heuristic filters for relationship-advice search (no structured DB columns).

Topic tags: phrase / word-boundary matching on title + body.
Block words: user list always enforced when non-empty; safe mode adds a default adult-term list.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Set, Tuple

# ── Default list used only when safe_mode is on ─────────────────────────────
_DEFAULT_NSFW_BLOCKLIST = frozenset(
    """
    nsfw porn pornographic xxx nude nudes naked sex tape onlyfans
    blowjob handjob cum orgasm erotic fetish bdsm
    """.split()
)

TAG_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "cheating": (
        "cheating",
        "cheat",
        "cheated",
        "affair",
        "infidelity",
        "unfaithful",
        "slept with",
        "hooked up with",
    ),
    "ldr": (
        "long distance",
        " ldr",
        "ldr ",
        " miles away",
        " different state",
        " different country",
        " timezone",
        "visiting him",
        "visiting her",
    ),
    "family": (
        "family",
        "mother",
        "father",
        "parent",
        "parents",
        "in-law",
        "in laws",
        "mother in law",
        "sibling",
        "brother",
        "sister",
        "my mom",
        "my dad",
    ),
    "breakup": (
        "break up",
        "breakup",
        "broke up",
        "dumped",
        "divorce",
        "split up",
        "ex boyfriend",
        "ex girlfriend",
        "ex-",
        "leaving him",
        "leaving her",
    ),
    "therapy": (
        "therapy",
        "therapist",
        "counseling",
        "counselling",
        "psychologist",
    ),
    "trust": (
        "dishonest",
        "snooped",
        "lying",
        "lied",
        "secret",
    ),
    "money": (
        "financial",
        "debt",
        "salary",
        "paying rent",
        "bills",
    ),
    "jealousy": (
        "jealous",
        "jealousy",
        "insecure",
        "possessive",
        "controlling",
    ),
}

# Standalone "trust" / "money" as whole words only (avoid "distrust", etc.)
_TAG_EXTRA_WORDS: Dict[str, Tuple[str, ...]] = {
    "trust": ("trust",),
    "money": ("money",),
}


def normalize_combined_text(title: str, body: str) -> str:
    return f"{title or ''}\n{body or ''}".lower()


def _phrase_matches(text_lower: str, phrase: str) -> bool:
    """Multi-word phrases: substring. Single tokens: word boundaries."""
    p = phrase.strip().lower()
    if not p:
        return False
    if " " in p or len(p) >= 14:
        return p in text_lower
    return re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", text_lower) is not None


def text_matches_any_blocked_term(text_lower: str, terms: Set[str]) -> bool:
    """True if any blocked term appears (whole words or full phrase)."""
    for raw in terms:
        w = raw.strip().lower()
        if not w:
            continue
        if " " in w:
            if w in text_lower:
                return True
        else:
            if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text_lower) is not None:
                return True
    return False


def tags_matched(text_lower: str, tag_ids: Sequence[str]) -> Set[str]:
    out: Set[str] = set()
    for tid in tag_ids:
        patterns = TAG_PATTERNS.get(tid)
        if not patterns:
            continue
        for phrase in patterns:
            if _phrase_matches(text_lower, phrase):
                out.add(tid)
                break
        if tid in out:
            continue
        for phrase in _TAG_EXTRA_WORDS.get(tid, ()):
            if _phrase_matches(text_lower, phrase):
                out.add(tid)
                break
    return out


def parse_request_filters(args) -> Dict[str, Any]:
    """Flask request.args-like mapping."""
    raw_tags = (args.get("tags") or "").strip()
    tag_ids = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
    tag_ids = [t for t in tag_ids if t in TAG_PATTERNS]

    safe_mode = str(args.get("safe_mode", "")).lower() in ("1", "true", "yes", "on")
    extra_block = (args.get("blockwords") or "").strip()
    extra_words: Set[str] = set()
    for part in re.split(r"[,;\n]+", extra_block):
        w = part.strip().lower()
        if w:
            extra_words.add(w)

    tag_mode = (args.get("tag_mode") or "boost").strip().lower()
    if tag_mode not in ("filter", "boost"):
        tag_mode = "boost"

    return {
        "tag_ids": tag_ids,
        "tag_mode": tag_mode,
        "safe_mode": safe_mode,
        "extra_block_words": extra_words,
    }


def passes_filters(
    text_lower: str,
    tags_hit: Set[str],
    filters: Dict[str, Any],
) -> Tuple[bool, str]:
    """Returns (keep, reason_if_drop)."""
    extra = filters["extra_block_words"]
    if extra and text_matches_any_blocked_term(text_lower, extra):
        return False, "blockwords"

    if filters["safe_mode"] and text_matches_any_blocked_term(text_lower, set(_DEFAULT_NSFW_BLOCKLIST)):
        return False, "safe_mode"

    tids = filters["tag_ids"]
    if tids and filters["tag_mode"] == "filter":
        if not tags_hit.intersection(set(tids)):
            return False, "tag_filter"

    return True, ""


def tag_boost_bonus(tags_hit: Set[str], requested: Sequence[str]) -> float:
    if not requested:
        return 0.0
    req = set(requested)
    overlap = len(tags_hit & req)
    return min(0.12, overlap * 0.04)


def filter_options_payload() -> Dict[str, Any]:
    return {
        "safe_mode_help": (
            "When enabled, hides posts that contain a built-in list of common adult / explicit terms."
        ),
        "blockwords_help": (
            "Always applied when this field is non-empty: posts containing any listed word or phrase "
            "(comma-separated) are removed. Whole words only for single tokens; use spaces for phrases."
        ),
    }
