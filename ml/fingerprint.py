"""
Account Fingerprinting
Computes a stable identity hash for an account listing based on its
parsed attributes, enabling:
  - group-aware train/test splits (same account never leaks across splits)
  - repost/duplicate detection across channels (Phase 2 dedup engine)

Two granularities:
  strict : every core attribute must match exactly (reposts with identical data)
  loose  : quantized attributes (tolerates OCR/parser drift between reposts)
"""

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

# Attributes that identify an account regardless of which channel posted it.
# Must exist (or degrade gracefully) in BOTH pipeline output and training CSV.
STRICT_ATTRS: list[str] = [
    "account_level",
    "collection_level",
    "mythics_count",
    "guns_count",
    "xsuits_count",
    "cars_total",
    "cars_mythic",
    "m4_type",
    "m4_level",
    "m4_is_max",
]

LOOSE_ATTRS: list[str] = [
    "account_level",   # quantized to buckets of 5
    "mythics_count",   # quantized to buckets of 10
    "m4_type",
    "m4_is_max",
]

_ITEM_SOURCES = ("canonical_items", "extracted_items_str")


def _normalize_value(value: Any) -> str:
    """Canonical string form: tolerant to '7' vs 7 vs 7.0 and case."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return str(int(round(value))) if value == value else ""  # NaN-safe
    if isinstance(value, (int,)):
        return str(value)
    return str(value).strip().lower()


def _quantize(value: Any, bucket: int) -> str:
    try:
        num = float(value)
        if num != num:  # NaN
            return ""
        return str(int(round(num / bucket)))
    except (TypeError, ValueError):
        return _normalize_value(value)


def _items_signature(attrs: Mapping[str, Any]) -> list[str]:
    """
    Canonical item signature. Prefers canonical_items / extracted_items_str;
    falls back to the individual has_* anchor flags so CSV rows without the
    joined strings still produce a stable items component.
    """
    for src in _ITEM_SOURCES:
        raw = attrs.get(src)
        if raw:
            if isinstance(raw, str):
                items = [s.strip() for s in raw.split(",") if s.strip()]
            else:
                items = [str(s).strip() for s in list(raw) if str(s).strip()]
            if items:
                return sorted({i.lower() for i in items})
    flags = sorted(
        k.replace("has_", "")
        for k, v in attrs.items()
        if k.startswith("has_") and _normalize_value(v) == "1"
    )
    return flags


def compute_fingerprint(attrs: Mapping[str, Any], loose: bool = False) -> str:
    """
    Deterministic fingerprint hash for an account listing.

    Args:
        attrs: mapping of parsed account attributes (pipeline output or CSV row)
        loose: quantized variant that tolerates minor parser drift
    Returns:
        16-char hex digest
    """
    payload: dict[str, Any] = {}
    keys = LOOSE_ATTRS if loose else STRICT_ATTRS
    buckets = {"account_level": 5, "mythics_count": 10} if loose else {}
    for key in keys:
        value = attrs.get(key)
        payload[key] = _quantize(value, buckets[key]) if key in buckets else _normalize_value(value)

    payload["items"] = _items_signature(attrs)

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:16]


_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def text_tokens(text: str) -> set:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def text_jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two ad texts (dedup helper)."""
    ta, tb = text_tokens(a), text_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
