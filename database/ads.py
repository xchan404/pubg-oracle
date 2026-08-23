"""
Sniped Ads Store (unified SQLAlchemy layer)
Single source of truth for ads captured by the sniper bot.
Replaces the legacy raw-sqlite `db/database.py` (db/sniper.db).
"""

import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from database.db import SessionLocal, init_db
from database.models import SnipedAd

logger = logging.getLogger("pubg_scraper")

LEGACY_SNIPER_DB = Path(__file__).resolve().parent.parent / "db" / "sniper.db"
LEGACY_MIGRATED_SUFFIX = ".migrated"


def migrate_legacy_sniper_db() -> int:
    """
    One-time migration: copy rows from the legacy db/sniper.db `ads` table
    into the unified database, then rename the legacy file to `.migrated`.
    Returns the number of migrated rows. Safe to call repeatedly.
    """
    if not LEGACY_SNIPER_DB.exists():
        return 0

    migrated = 0
    try:
        legacy_conn = sqlite3.connect(LEGACY_SNIPER_DB)
        legacy_conn.row_factory = sqlite3.Row
        cursor = legacy_conn.execute(
            "SELECT chat_id, message_id, raw_text, asked_price, fair_value, "
            "profit, segment, parsed_data, timestamp FROM ads"
        )
        rows = cursor.fetchall()
        legacy_conn.close()

        session = SessionLocal()
        try:
            for row in rows:
                exists = (
                    session.query(SnipedAd)
                    .filter(
                        SnipedAd.chat_id == row["chat_id"],
                        SnipedAd.message_id == row["message_id"],
                    )
                    .first()
                )
                if exists:
                    continue
                ts = row["timestamp"]
                parsed_ts = None
                if ts:
                    try:
                        parsed_ts = datetime.fromisoformat(str(ts))
                    except ValueError:
                        parsed_ts = None
                session.add(
                    SnipedAd(
                        chat_id=row["chat_id"],
                        message_id=row["message_id"],
                        raw_text=row["raw_text"],
                        asked_price=row["asked_price"],
                        fair_value=row["fair_value"],
                        profit=row["profit"],
                        segment=row["segment"],
                        parsed_data=row["parsed_data"],
                        timestamp=parsed_ts or datetime.utcnow(),
                    )
                )
                migrated += 1
            session.commit()
        finally:
            session.close()

        backup_path = LEGACY_SNIPER_DB.with_suffix(LEGACY_MIGRATED_SUFFIX)
        shutil.move(str(LEGACY_SNIPER_DB), str(backup_path))
        logger.info(
            f"Legacy sniper DB migrated: {migrated} rows copied, "
            f"original moved to {backup_path.name}"
        )
    except Exception as e:
        logger.error(f"Legacy sniper DB migration failed: {e}")
    return migrated


def save_ad(
    chat_id: int,
    message_id: int,
    raw_text: str,
    asked_price: float | None,
    fair_value: float,
    profit: float | None,
    segment: str,
    parsed_data: dict[str, Any],
) -> bool:
    """Save ad to the unified DB. True if new, False if it already exists."""
    session = SessionLocal()
    try:
        exists = (
            session.query(SnipedAd)
            .filter(
                SnipedAd.chat_id == chat_id,
                SnipedAd.message_id == message_id,
            )
            .first()
        )
        if exists:
            return False

        session.add(
            SnipedAd(
                chat_id=chat_id,
                message_id=message_id,
                raw_text=raw_text,
                asked_price=asked_price,
                fair_value=fair_value,
                profit=profit,
                segment=segment,
                parsed_data=json.dumps(parsed_data, ensure_ascii=False, default=str),
            )
        )
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving ad: {e}")
        return False
    finally:
        session.close()


def initialize() -> None:
    """Create tables in the unified DB and pull in any legacy data."""
    init_db()
    migrate_legacy_sniper_db()
