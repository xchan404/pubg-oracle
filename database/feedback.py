"""
Feedback Store (Phase 3 flywheel)
Persists human labels on sniped ads and serves verified sale prices
to the training pipeline. Every tap on a bot inline button lands here.
"""

import json
import logging
from typing import Any

from database.db import SessionLocal
from database.models import DealFeedback, SnipedAd

logger = logging.getLogger("pubg_scraper")

VALID_LABELS = {"bought", "sold_price", "not_a_deal", "wrong_parse", "scam"}


def save_feedback(
    chat_id: int,
    message_id: int,
    label: str,
    value_egp: float | None = None,
    corrected_data: dict[str, Any] | None = None,
    fingerprint: str | None = None,
) -> bool:
    """
    Records a human label. True if new, False if this ad already has
    the same label (unique constraint) or the input was invalid.
    """
    if label not in VALID_LABELS:
        logger.warning(f"Rejected invalid feedback label: {label}")
        return False

    session = SessionLocal()
    try:
        exists = (
            session.query(DealFeedback)
            .filter(
                DealFeedback.chat_id == chat_id,
                DealFeedback.message_id == message_id,
                DealFeedback.label == label,
            )
            .first()
        )
        if exists:
            return False

        session.add(
            DealFeedback(
                chat_id=chat_id,
                message_id=message_id,
                label=label,
                value_egp=value_egp,
                corrected_data=json.dumps(corrected_data, ensure_ascii=False)
                if corrected_data else None,
                fingerprint=fingerprint,
            )
        )
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving feedback: {e}")
        return False
    finally:
        session.close()


def get_label_stats() -> dict[str, Any]:
    """Label counts per type + verified sale count for telemetry."""
    session = SessionLocal()
    try:
        from sqlalchemy import func

        rows = (
            session.query(DealFeedback.label, func.count(DealFeedback.id))
            .group_by(DealFeedback.label)
            .all()
        )
        counts = {label: int(n) for label, n in rows}
        verified = counts.get("bought", 0) + counts.get("sold_price", 0)
        return {
            "labels_total": sum(counts.values()),
            "labels_by_type": counts,
            "verified_sales": verified,
        }
    except Exception as e:
        logger.error(f"Error reading feedback stats: {e}")
        return {"labels_total": 0, "labels_by_type": {}, "verified_sales": 0}
    finally:
        session.close()


def get_positions() -> list[dict[str, Any]]:
    """
    Portfolio view: every 'bought' label becomes a position (cost = asking
    price); a matching 'sold_price' label closes it with actual revenue.
    """
    session = SessionLocal()
    try:
        bought = (
            session.query(SnipedAd, DealFeedback)
            .join(
                DealFeedback,
                (DealFeedback.chat_id == SnipedAd.chat_id)
                & (DealFeedback.message_id == SnipedAd.message_id),
            )
            .filter(DealFeedback.label == "bought")
            .order_by(DealFeedback.created_at.desc())
            .all()
        )
        sold_map: dict[tuple, float] = {}
        sold_rows = (
            session.query(DealFeedback)
            .filter(
                DealFeedback.label == "sold_price",
                DealFeedback.value_egp.isnot(None),
            )
            .all()
        )
        for fb in sold_rows:
            sold_map[(fb.chat_id, fb.message_id)] = float(fb.value_egp)

        positions = []
        for ad, _fb in bought:
            positions.append({
                "chat_id": ad.chat_id,
                "message_id": ad.message_id,
                "asked_price": ad.asked_price,
                "sold_price": sold_map.get((ad.chat_id, ad.message_id)),
                "segment": ad.segment,
                "timestamp": ad.timestamp,
            })
        return positions
    except Exception as e:
        logger.error(f"Error loading portfolio positions: {e}")
        return []
    finally:
        session.close()


def get_verified_sales(limit: int | None = None) -> list[dict[str, Any]]:
    """
    Verified ground-truth sales: ads labeled bought/sold_price with an
    actual price. Joined back to the original raw text so the dataset
    builder can re-run the parser and swap in the true price.
    """
    session = SessionLocal()
    try:
        query = (
            session.query(SnipedAd, DealFeedback)
            .join(
                DealFeedback,
                (DealFeedback.chat_id == SnipedAd.chat_id)
                & (DealFeedback.message_id == SnipedAd.message_id),
            )
            .filter(
                DealFeedback.label.in_(["bought", "sold_price"]),
                DealFeedback.value_egp.isnot(None),
            )
            .order_by(DealFeedback.created_at.desc())
        )
        if limit:
            query = query.limit(limit)

        out = []
        for ad, fb in query.all():
            out.append({
                "chat_id": ad.chat_id,
                "message_id": ad.message_id,
                "raw_text": ad.raw_text,
                "asked_price": ad.asked_price,
                "actual_price": float(fb.value_egp),
                "fingerprint": fb.fingerprint or "",
            })
        return out
    except Exception as e:
        logger.error(f"Error loading verified sales: {e}")
        return []
    finally:
        session.close()
