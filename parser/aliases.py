"""
PUBG Market Intelligence - Knowledge Base Loader
Item definitions live in config/knowledge_base.yaml (versioned, editable
without code changes). This module loads them into KNOWLEDGE_BASE and
provides alias resolution utilities.
"""

from pathlib import Path

import yaml

KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent.parent / "config" / "knowledge_base.yaml"


def _load_knowledge_base() -> dict:
    with open(KNOWLEDGE_BASE_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    items = data.get("items", {})
    if not items:
        raise ValueError(f"No items found in knowledge base: {KNOWLEDGE_BASE_PATH}")
    return items


KNOWLEDGE_BASE = _load_knowledge_base()


def resolve_alias(word: str, similarity_threshold: float = 0.82) -> str | None:
    """
    Given a word or phrase, returns the canonical item ID from KNOWLEDGE_BASE.
    Uses exact matching first, followed by fuzzy string matching.
    """
    if not word or not isinstance(word, str):
        return None

    word_clean = word.strip().lower()
    if not word_clean:
        return None

    # 1. Exact match check
    for item_id, data in KNOWLEDGE_BASE.items():
        if word_clean in [a.lower() for a in data["aliases"]]:
            return item_id

    # 2. Fuzzy match fallback
    import difflib
    best_match = None
    best_ratio = 0.0

    for item_id, data in KNOWLEDGE_BASE.items():
        for alias in data["aliases"]:
            alias_lower = alias.lower()
            # Calculate similarity
            ratio = difflib.SequenceMatcher(None, word_clean, alias_lower).ratio()
            if ratio > best_ratio and ratio >= similarity_threshold:
                best_ratio = ratio
                best_match = item_id

    return best_match


def resolve_text_items(text: str) -> list:
    """
    Scans a given text string and resolves all canonical items present in it.
    Returns a list of unique canonical item IDs.
    """
    if not text:
        return []

    found_items = set()
    text_lower = text.lower()

    for item_id, data in KNOWLEDGE_BASE.items():
        for alias in data["aliases"]:
            if alias.lower() in text_lower:
                found_items.add(item_id)
                break

    return list(found_items)


def get_item_info(item_id: str) -> dict:
    """Returns metadata for a given canonical item ID."""
    return KNOWLEDGE_BASE.get(item_id, {})

