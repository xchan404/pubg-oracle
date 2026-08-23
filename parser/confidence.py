"""
Parse Confidence Estimator
Scores how completely the regex parser understood an ad (0.0 - 1.0).
Low confidence triggers the LLM fallback (if configured) and feeds the
active-learning review queue.
"""

from typing import Any

# Field presence weights — price and the M4 anchor dominate value
FIELD_WEIGHTS: dict[str, float] = {
    "price_egp": 0.25,
    "m4_present": 0.20,
    "account_level": 0.15,
    "mythics_count": 0.15,
    "guns_count": 0.10,
    "items": 0.10,
    "cars": 0.05,
}

MIN_TEXT_LENGTH = 12


def estimate_parse_confidence(parsed: dict[str, Any]) -> float:
    """
    Weighted field-presence score for a pipeline output dict.
    Never raises; unknown/missing fields simply contribute 0.
    """
    if not isinstance(parsed, dict):
        return 0.0

    text_len = len(str(parsed.get("clean_text") or ""))
    if text_len < MIN_TEXT_LENGTH:
        # Not enough signal to trust any extraction
        return round(min(0.2, text_len / MIN_TEXT_LENGTH * 0.2), 3)

    m4_present = bool(
        parsed.get("m4_type")
        or parsed.get("has_m4_glacier")
        or parsed.get("has_joker_fox")
        or parsed.get("m4_2_type")
        or parsed.get("m4_3_type")
    )
    checks = {
        "price_egp": float(parsed.get("price_egp") or 0) > 0,
        "m4_present": m4_present,
        "account_level": float(parsed.get("account_level") or 0) > 0,
        "mythics_count": float(parsed.get("mythics_count") or 0) > 0,
        "guns_count": float(parsed.get("guns_count") or 0) > 0,
        "items": bool(parsed.get("canonical_items")),
        "cars": float(parsed.get("cars_mythic") or 0) > 0
        or float(parsed.get("cars_total") or 0) > 0,
    }
    score = sum(w for k, w in FIELD_WEIGHTS.items() if checks.get(k))
    return round(min(1.0, score), 3)
