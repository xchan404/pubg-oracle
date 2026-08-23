"""
Market Data Layer
Builds the enriched analytical dataset used by all intelligence engines:
parsed listing features (CSV snapshot) joined with real posting timestamps
from the unified SQLite database, cached as parquet.

Engines consume plain DataFrames; only this module touches storage.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

CSV_PATH = PROJECT_ROOT / "data" / "parsed" / "csv" / "all_parsed_accounts.csv"
DB_PATH = PROJECT_ROOT / "data" / "raw" / "sqlite" / "pubg_accounts.db"
CACHE_DIR = PROJECT_ROOT / "data" / "analytics"
CACHE_PATH = CACHE_DIR / "market_enriched.parquet"

_CACHE: pd.DataFrame | None = None


def _load_db_enrichment(db_path: Path) -> pd.DataFrame:
    """Timestamps + canonical item strings from the unified database."""
    conn = sqlite3.connect(db_path)
    try:
        enriched = pd.read_sql_query(
            """
            SELECT r.channel_username, r.message_id, r.date AS _date,
                   COALESCE(p.extracted_items_str, '') AS extracted_items_str
            FROM raw_messages r
            LEFT JOIN parsed_accounts p
              ON p.channel_username = r.channel_username
             AND p.message_id = r.message_id
            """,
            conn,
        )
    finally:
        conn.close()
    enriched["posted_at"] = pd.to_datetime(enriched["_date"], errors="coerce", utc=True)
    return enriched.drop(columns=["_date"])


def _fill_missing_items(df: pd.DataFrame) -> pd.DataFrame:
    """Recomputes canonical items from text for rows the DB couldn't provide."""
    from parser.aliases import resolve_text_items

    mask = df["extracted_items_str"].fillna("").eq("")
    if not mask.any():
        return df
    recomputed = df.loc[mask, "clean_text"].fillna("").map(
        lambda t: ",".join(sorted(resolve_text_items(t)))
    )
    df.loc[mask, "extracted_items_str"] = recomputed
    return df


def load_market_dataframe(force_refresh: bool = False) -> pd.DataFrame:
    """
    Returns listings with parsed features + posted_at timestamps.
    Rows without a DB timestamp (e.g. web-evaluator appends) are dropped,
    since every time-series engine requires a real posting date.
    """
    global _CACHE
    if _CACHE is not None and not force_refresh:
        return _CACHE

    if CACHE_PATH.exists() and not force_refresh:
        cache_mtime = CACHE_PATH.stat().st_mtime
        if CSV_PATH.exists() and CSV_PATH.stat().st_mtime <= cache_mtime:
            _CACHE = pd.read_parquet(CACHE_PATH)
            return _CACHE

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Parsed dataset not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, low_memory=False)

    if "extracted_items_str" not in df.columns:
        df["extracted_items_str"] = ""

    dropped = 0
    if DB_PATH.exists():
        enrich = _load_db_enrichment(DB_PATH)
        df = df.merge(enrich, on=["channel_username", "message_id"], how="left")
        before = len(df)
        df = df.dropna(subset=["posted_at"]).reset_index(drop=True)
        dropped = before - len(df)

        # Merge produced suffixed columns; prefer DB items, fall back to local
        if "extracted_items_str_x" in df.columns:
            merged = df["extracted_items_str_y"].fillna(df["extracted_items_str_x"])
            df = df.drop(columns=["extracted_items_str_x", "extracted_items_str_y"])
            df["extracted_items_str"] = merged
    else:
        df["posted_at"] = pd.NaT
        df = df.dropna(subset=["posted_at"]).reset_index(drop=True)
        dropped = len(df)

    df = _fill_missing_items(df)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_PATH, index=False)
    _CACHE = df
    print(f"[market_data] enriched dataset: {len(df):,} dated listings "
          f"(dropped {dropped:,} without timestamps)")
    return _CACHE


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    enriched = load_market_dataframe(force_refresh="--refresh" in sys.argv)
    print(enriched["posted_at"].agg(["min", "max"]))
    print(enriched.groupby(enriched["posted_at"].dt.to_period("M")).size().tail(12))
