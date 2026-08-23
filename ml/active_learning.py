"""
Active Learning Review Queue (Phase 3)
Surfaces recent sniper ads the model is LEAST sure about, so the human
labels where they matter most. Consumed by the bot's /review command and
by telemetry.
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import SessionLocal
from database.models import SnipedAd


def _confidence_from_prediction(prediction: dict[str, Any]) -> int:
    try:
        return int(str(prediction.get("confidence", {}).get("score", "0")).rstrip("%"))
    except (ValueError, AttributeError):
        return 0


def select_review_queue(limit: int = 5, max_age_days: int = 14,
                        pricer: Any | None = None) -> list[dict[str, Any]]:
    """
    Returns the most recent ads sorted by model confidence (ascending).
    Each item: {chat_id, message_id, excerpt, asked_price, fair_value,
                confidence_pct, segment}
    """
    if pricer is None:
        from ml.predict import EnsemblePricer
        try:
            pricer = EnsemblePricer()
        except Exception as e:  # pragma: no cover - models missing
            print(f"[WARN] Pricer unavailable for review queue: {e}")
            return []

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=max_age_days)
    session = SessionLocal()
    try:
        ads = (
            session.query(SnipedAd)
            .filter(SnipedAd.timestamp >= cutoff)
            .order_by(SnipedAd.timestamp.desc())
            .limit(200)
            .all()
        )
    finally:
        session.close()

    scored = []
    for ad in ads:
        text = ad.raw_text or ""
        try:
            res = pricer.predict(text)
        except Exception:
            continue
        scored.append({
            "chat_id": ad.chat_id,
            "message_id": ad.message_id,
            "excerpt": text[:120],
            "asked_price": ad.asked_price,
            "fair_value": res.get("fair_value_egp"),
            "segment": res.get("segment", ""),
            "confidence_pct": _confidence_from_prediction(res),
            "_ts": ad.timestamp or datetime.utcnow(),
        })

    scored.sort(key=lambda r: (r["confidence_pct"], -r["_ts"].timestamp()))
    return scored[:limit]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for item in select_review_queue(limit=int(os.environ.get("REVIEW_LIMIT", "5"))):
        print(json.dumps(item, ensure_ascii=False))
