"""
LLM Fallback Extractor
When regex confidence is low and an OpenAI-compatible endpoint is
configured (env: LLM_FALLBACK_ENABLED, OPENAI_API_KEY, OPENAI_BASE_URL,
OPENAI_MODEL), asks the model to extract structured fields from the ad.

Safety policy:
  - NEVER overrides fields the regex parser already found (fill-missing-only,
    unless LLM_OVERRIDE=1)
  - item ids are constrained to the knowledge base vocabulary
  - every call's outcome (including disagreements) is logged to
    logs/llm_fallback.jsonl so disagreements can be distilled into new rules
  - any failure returns the input unchanged — the pipeline never breaks
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("pubg_scraper")

LOG_PATH = Path("logs") / "llm_fallback.jsonl"

FILLABLE_FIELDS = [
    "account_level", "mythics_count", "guns_count", "xsuits_count",
    "m4_level", "m4_is_max", "cars_mythic", "price_egp",
]

ITEM_VOCAB_URL = "parser.aliases:KNOWLEDGE_BASE"  # documentation pointer only


def _enabled() -> bool:
    return (
        os.getenv("LLM_FALLBACK_ENABLED", "").lower() in ("1", "true", "yes")
        and bool(os.getenv("OPENAI_API_KEY"))
    )


def _override() -> bool:
    return os.getenv("LLM_OVERRIDE", "").lower() in ("1", "true", "yes")


def _threshold() -> float:
    try:
        return float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.55"))
    except ValueError:
        return 0.55


def _build_prompt(raw_text: str, vocab: list[str]) -> str:
    vocab_list = ", ".join(vocab[:80])
    return (
        "You extract PUBG Mobile account attributes from Arabic sale ads.\n"
        "Return STRICT JSON only, no markdown. Use null for unknown values.\n"
        f"Allowed item ids: [{vocab_list}]\n"
        'Schema: {"account_level": int|null, "mythics_count": int|null, '
        '"guns_count": int|null, "xsuits_count": int|null, '
        '"m4_level": int|null, "m4_is_max": bool|null, '
        '"cars_mythic": int|null, "price_egp": number|null, '
        '"items": string[]}\n\n'
        f"Ad text:\n{raw_text[:1500]}"
    )


def _call_llm(prompt: str) -> dict[str, Any] | None:
    """
    Calls an OpenAI-compatible chat completion endpoint.
    Isolated for testability (tests monkeypatch this).
    """
    import httpx

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY", "")

    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a precise JSON extractor."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "12")),
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _log_event(event: dict[str, Any]) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {"timestamp": datetime.now(UTC).isoformat(), **event}
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # pragma: no cover - logging must never raise
        logger.debug(f"llm fallback log failed: {e}")


def maybe_llm_augment(parsed: dict[str, Any], raw_text: str,
                      confidence: float) -> dict[str, Any]:
    """
    Entry point used by the pipeline. Returns the (possibly enriched) dict.
    Guaranteed non-throwing; on any problem the original dict is returned.
    """
    if not _enabled() or confidence >= _threshold():
        parsed["parse_confidence"] = round(confidence, 3)
        return parsed

    vocab: list[str] = []
    try:
        from parser.aliases import KNOWLEDGE_BASE
        vocab = list(KNOWLEDGE_BASE.keys())
    except Exception:
        pass

    filled: list[str] = []
    disagreements: list[dict[str, Any]] = []
    try:
        llm = _call_llm(_build_prompt(raw_text or "", vocab))
        if not isinstance(llm, dict):
            raise ValueError("LLM returned non-object")

        for field in FILLABLE_FIELDS:
            incoming = llm.get(field)
            current = parsed.get(field)
            if incoming is None or incoming == "":
                continue
            missing_current = current is None or current == "" or current == 0
            if missing_current or _override():
                if not missing_current and current != incoming:
                    disagreements.append(
                        {"field": field, "regex": current, "llm": incoming}
                    )
                parsed[field] = incoming
                filled.append(field)

        # Items: union, constrained to vocabulary
        llm_items = [i for i in (llm.get("items") or []) if i in vocab]
        if llm_items:
            existing = set(parsed.get("canonical_items") or [])
            merged = sorted(existing | set(llm_items))
            added = sorted(set(llm_items) - existing)
            if added:
                filled.extend(added)
                disagreements.append({"field": "items", "added": added})
            parsed["canonical_items"] = merged
            parsed["extracted_items_str"] = ",".join(merged)

        parsed["parse_confidence"] = round(confidence, 3)
        parsed["llm_augmented"] = bool(filled)
        _log_event({
            "event": "augment",
            "confidence_before": confidence,
            "filled": filled,
            "disagreements": disagreements,
            "override": _override(),
        })
    except Exception as e:
        _log_event({"event": "error", "error": str(e),
                    "confidence_before": confidence})
    return parsed
