"""
Data Freshness Monitor (Week 1)
Answers the only question that matters for a market-intelligence product:
"how old is the newest listing?"

Read-only by design: opens SQLite in `mode=ro` so it can run from health
checks and dashboards without ever taking a write lock.
"""

import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "raw" / "sqlite" / "pubg_accounts.db"

DEFAULT_STALE_HOURS = 24.0


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_freshness(db_path: Path | str | None = None,
                  stale_after_hours: float = DEFAULT_STALE_HOURS) -> dict:
    """Returns freshness KPIs for the listings store."""
    path = Path(db_path) if db_path else DB_PATH
    empty = {
        "status": "missing",
        "is_stale": True,
        "last_listing_at": None,
        "hours_since_last": None,
        "listings_total": 0,
        "listings_24h": 0,
        "listings_7d": 0,
        "channels_24h": 0,
        "stale_after_hours": stale_after_hours,
    }
    if not path.exists():
        return empty

    uri = f"file:{quote(path.as_posix())}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error:
        return {**empty, "status": "unreadable"}

    try:
        total = conn.execute("SELECT COUNT(*) FROM raw_messages").fetchone()[0]
        if not total:
            return {**empty, "status": "empty"}

        last_raw = conn.execute("SELECT MAX(date) FROM raw_messages").fetchone()[0]
        now = datetime.now(UTC)
        cutoff_24 = (now - timedelta(hours=24)).isoformat()
        cutoff_7d = (now - timedelta(days=7)).isoformat()

        listings_24h = conn.execute(
            "SELECT COUNT(*) FROM raw_messages WHERE date >= ?", (cutoff_24,)
        ).fetchone()[0]
        listings_7d = conn.execute(
            "SELECT COUNT(*) FROM raw_messages WHERE date >= ?", (cutoff_7d,)
        ).fetchone()[0]
        channels_24h = conn.execute(
            "SELECT COUNT(DISTINCT channel_username) FROM raw_messages WHERE date >= ?",
            (cutoff_24,),
        ).fetchone()[0]
    except sqlite3.Error:
        return {**empty, "status": "unreadable"}
    finally:
        conn.close()

    last_dt = _parse_ts(last_raw)
    hours_since = round((now - last_dt).total_seconds() / 3600, 1) if last_dt else None
    is_stale = hours_since is None or hours_since > stale_after_hours

    return {
        "status": "stale" if is_stale else "fresh",
        "is_stale": is_stale,
        "last_listing_at": last_dt.isoformat() if last_dt else None,
        "hours_since_last": hours_since,
        "listings_total": int(total),
        "listings_24h": int(listings_24h),
        "listings_7d": int(listings_7d),
        "channels_24h": int(channels_24h),
        "stale_after_hours": stale_after_hours,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import json

    print(json.dumps(get_freshness(), ensure_ascii=False, indent=2))
