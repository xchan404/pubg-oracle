"""
Price Repair (Week 1 data quality)
Re-parses listings whose stored price is implausible after the parser fix
for redundant "الف" suffixes ("السعر: 84500 الف ج" -> 84,500 not 84.5M).

Updates both storage layers:
  - data/raw/sqlite/pubg_accounts.db  (parsed_accounts.price_egp/price_usd)
  - data/parsed/csv/all_parsed_accounts.csv (training source)

Usage:
    python scripts/repair_prices.py            # dry run, prints what would change
    python scripts/repair_prices.py --apply    # writes changes
"""

import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from parser.regex_parser import extract_prices  # noqa: E402
from parser.text_cleaner import clean_text  # noqa: E402

DB_PATH = PROJECT_ROOT / "data" / "raw" / "sqlite" / "pubg_accounts.db"
CSV_PATH = PROJECT_ROOT / "data" / "parsed" / "csv" / "all_parsed_accounts.csv"
MARKET_CACHE = PROJECT_ROOT / "data" / "analytics" / "market_enriched.parquet"

SUSPICIOUS_MAX = 500_000
SUSPICIOUS_MIN = 100


def find_suspicious(conn: sqlite3.Connection) -> list[tuple]:
    cur = conn.execute(
        """
        SELECT p.channel_username, p.message_id, p.price_egp, r.text
        FROM parsed_accounts p
        LEFT JOIN raw_messages r
          ON r.channel_username = p.channel_username
         AND r.message_id = p.message_id
        WHERE p.price_egp IS NOT NULL
          AND (p.price_egp > ? OR p.price_egp < ?)
        ORDER BY p.price_egp DESC
        """,
        (SUSPICIOUS_MAX, SUSPICIOUS_MIN),
    )
    return cur.fetchall()


def build_changes(rows: list[tuple]) -> tuple[list[tuple], dict[str, Any]]:
    changes: list[tuple] = []
    stats: dict[str, Any] = {
        "suspicious": len(rows),
        "repaired": 0,
        "dropped": 0,
        "unchanged": 0,
        "missing_text": 0,
        "repaired_examples": [],
    }
    for channel, message_id, old_price, text in rows:
        if not text:
            stats["missing_text"] += 1
            continue
        new_egp, new_usd = extract_prices(clean_text(text))
        if new_egp is None:
            changes.append((None, new_usd, channel, message_id))
            stats["dropped"] += 1
            continue
        if new_egp == old_price:
            stats["unchanged"] += 1
            continue
        changes.append((new_egp, new_usd, channel, message_id))
        stats["repaired"] += 1
        if len(stats["repaired_examples"]) < 10:
            stats["repaired_examples"].append(
                {"channel": channel, "message_id": message_id,
                 "old": old_price, "new": new_egp}
            )
    return changes, stats


def apply_to_db(conn: sqlite3.Connection, changes: list[tuple]) -> None:
    conn.executemany(
        """
        UPDATE parsed_accounts
        SET price_egp = ?, price_usd = COALESCE(?, price_usd)
        WHERE channel_username = ? AND message_id = ?
        """,
        changes,
    )
    conn.commit()


def apply_to_csv(changes: list[tuple]) -> int:
    if not CSV_PATH.exists():
        return 0
    df = pd.read_csv(CSV_PATH, low_memory=False)
    if "channel_username" not in df.columns or "message_id" not in df.columns:
        return 0

    lookup = {(ch, int(mid)): (egp, usd) for egp, usd, ch, mid in changes}
    mask = [
        (str(ch), int(mid)) in lookup
        for ch, mid in zip(df["channel_username"], df["message_id"], strict=False)
    ]
    if not any(mask):
        return 0

    idx = df.index[mask]
    for i in idx:
        egp, usd = lookup[(str(df.at[i, "channel_username"]), int(df.at[i, "message_id"]))]
        df.at[i, "price_egp"] = egp
        if usd is not None:
            df.at[i, "price_usd"] = usd

    backup = Path(tempfile.gettempdir()) / "opencode" / (CSV_PATH.stem + ".pre_price_repair.csv")
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(CSV_PATH, backup)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    return int(len(idx))


def repair_via_copy(db_path: Path) -> tuple[list[tuple], dict]:
    """
    Repairs a temp copy, then swaps it in. This keeps the live DB untouched
    on failure and avoids journal-file creation next to the original.
    """
    work_dir = Path(tempfile.gettempdir()) / "opencode"
    work_dir.mkdir(parents=True, exist_ok=True)
    work_db = work_dir / "pubg_repair_work.db"
    safety = work_dir / "pubg_repair_pre_swap.db"

    shutil.copy2(db_path, work_db)

    conn = sqlite3.connect(work_db, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=MEMORY")
        rows = find_suspicious(conn)
        changes, stats = build_changes(rows)
        apply_to_db(conn, changes)
    finally:
        conn.close()

    shutil.copy2(db_path, safety)
    shutil.copy2(work_db, db_path)

    # A stale WAL/SHM beside the swapped file would roll old pages back in.
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

    check = sqlite3.connect(db_path, timeout=30)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        raise RuntimeError(f"post-swap integrity check failed: {result}")

    return changes, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair implausible parsed prices")
    parser.add_argument("--apply", action="store_true", help="write changes")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    if args.apply:
        changes, stats = repair_via_copy(DB_PATH)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            rows = find_suspicious(conn)
            changes, stats = build_changes(rows)
        finally:
            conn.close()

    print(f"[repair] suspicious rows: {stats['suspicious']:,}")
    print(f"[repair] repaired: {stats['repaired']:,} | "
          f"dropped: {stats['dropped']:,} | unchanged: {stats['unchanged']:,} | "
          f"missing text: {stats['missing_text']:,}")
    for ex in stats["repaired_examples"]:
        print(f"   {ex['channel']}#{ex['message_id']}: "
              f"{ex['old']:,.0f} -> {ex['new']:,.0f} EGP")

    if not args.apply:
        print("\n[dry-run] pass --apply to write changes")
        return

    csv_rows = apply_to_csv(changes)
    if MARKET_CACHE.exists():
        MARKET_CACHE.unlink()
        print("[repair] market cache invalidated (will rebuild on next query)")
    print(f"[repair] DB updated: {len(changes):,} rows | CSV updated: {csv_rows:,} rows")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
