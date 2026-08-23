"""
Repost & Listing Lifecycle Engine
Clusters listings by account fingerprint to expose:
  - how often the same account is reposted (and by which channels)
  - asking-price trajectories across reposts (drops, bumps)
  - sold-marker detection on the latest repost of each cluster
Pure functions over DataFrames — no storage access.
"""

import re
from typing import Any

import numpy as np
import pandas as pd

from ml.fingerprint import compute_fingerprint

SOLD_PATTERN = re.compile(
    r"تم\s*البيع|تم\s*بيع|اتبععت?|مباع|انباعت?|اتشترت|sold\b", re.IGNORECASE
)

PRICE_TOLERANCE_PCT = 0.60  # same fingerprint must ask within ±60% to count


def ensure_fingerprints(df: pd.DataFrame) -> pd.DataFrame:
    if "account_fingerprint" in df.columns:
        return df
    fps = df.apply(lambda r: compute_fingerprint(r.to_dict()), axis=1)
    out = df.copy()
    out["account_fingerprint"] = fps
    return out


def build_clusters(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per account fingerprint with lifecycle aggregates.
    Requires posted_at; price columns optional.
    """
    work = ensure_fingerprints(df).sort_values("posted_at")
    has_price = "price_egp" in work.columns

    agg_spec: dict[str, Any] = {
        "posted_at": ["min", "max", "count"],
    }
    if has_price:
        agg_spec["price_egp"] = ["min", "max", "first", "last"]

    grouped = work.groupby("account_fingerprint").agg(agg_spec)
    grouped.columns = ["_".join(str(p) for p in part) for part in grouped.columns]
    grouped = grouped.rename(columns={
        "posted_at_min": "first_seen",
        "posted_at_max": "last_seen",
        "posted_at_count": "n_posts",
        "price_egp_min": "price_min",
        "price_egp_max": "price_max",
        "price_egp_first": "price_first",
        "price_egp_last": "price_last",
    })

    channels = (
        work.groupby("account_fingerprint")["channel_username"]
        .apply(lambda s: sorted(set(s.dropna())))
        .rename("channels")
    )
    grouped = grouped.join(channels)

    # Drop accidental fingerprint collisions (same attrs, wildly different price)
    if "price_min" in grouped.columns:
        spread_ok = (grouped["price_max"] - grouped["price_min"]) <= \
            grouped["price_min"].clip(lower=1) * PRICE_TOLERANCE_PCT * 2
        grouped = grouped[spread_ok | grouped["price_max"].isna()]

    grouped["days_on_market"] = (
        (grouped["last_seen"] - grouped["first_seen"]).dt.total_seconds() / 86400
    ).round(1)
    return grouped.reset_index()


def detect_sold_markers(df: pd.DataFrame) -> pd.DataFrame:
    """Flags rows whose text contains sold markers."""
    out = df.copy()
    text_col = "clean_text" if "clean_text" in out.columns else "raw_text"
    out["is_sold_marker"] = (
        out[text_col].fillna("").astype(str).str.contains(SOLD_PATTERN)
    )
    return out


def get_repost_summary(df: pd.DataFrame, top_n: int = 15) -> dict[str, Any]:
    """
    Market-wide repost analytics:
      cluster counts, multi-channel spread, top reposted accounts,
      median days-on-market for multi-post accounts.
    """
    work = ensure_fingerprints(df)
    clusters = build_clusters(work)
    multi = clusters[clusters["n_posts"] > 1].copy()

    df_sold = detect_sold_markers(work)
    sold_by_fp = df_sold.groupby("account_fingerprint")["is_sold_marker"].any()

    summary: dict[str, Any] = {
        "total_listings": int(len(df)),
        "unique_accounts": int(len(clusters)),
        "reposted_accounts": int(len(multi)),
        "repost_share_pct": round(len(multi) / max(1, len(clusters)) * 100, 1),
        "median_reposts_per_reposted_account": float(multi["n_posts"].median()) if len(multi) else 0.0,
        "max_reposts_observed": int(clusters["n_posts"].max()),
        "multi_channel_accounts": int(
            multi["channels"].apply(len).gt(1).sum()
        ) if len(multi) else 0,
        "median_days_on_market_reposted": float(multi["days_on_market"].median()) if len(multi) else None,
        "sold_marker_accounts": int(sold_by_fp.sum()),
    }

    if "price_last" in multi.columns and "price_first" in multi.columns:
        valid = multi.dropna(subset=["price_first", "price_last"])
        valid = valid[valid["price_first"] > 0]
        if len(valid):
            drops = (valid["price_first"] - valid["price_last"]) / valid["price_first"] * 100
            summary["accounts_with_price_drop_pct"] = round(float((drops > 5).mean() * 100), 1)
            summary["median_price_change_pct"] = round(float(-drops.median()), 1)

    multi["channel_span"] = multi["channels"].apply(len)
    top = multi.nlargest(top_n, "n_posts")
    summary["top_reposts"] = [
        {
            "fingerprint": row.account_fingerprint,
            "posts": int(row.n_posts),
            "channels": list(row.channels)[:6],
            "days_on_market": float(row.days_on_market),
            "price_first": None if pd.isna(getattr(row, "price_first", np.nan)) else round(float(row.price_first)),
            "price_last": None if pd.isna(getattr(row, "price_last", np.nan)) else round(float(row.price_last)),
            "still_listed": not bool(sold_by_fp.get(row.account_fingerprint, False)),
        }
        for row in top.itertuples()
    ]
    return summary


def get_listing_timeline(df: pd.DataFrame, fingerprint: str) -> dict[str, Any]:
    """Full repost timeline for one account fingerprint."""
    work = ensure_fingerprints(df)
    rows = work[work["account_fingerprint"] == fingerprint].sort_values("posted_at")
    if rows.empty:
        return {"error": "unknown fingerprint"}

    events = []
    for _, r in rows.iterrows():
        events.append({
            "posted_at": r["posted_at"].isoformat(),
            "channel": r["channel_username"],
            "asking_price": None if pd.isna(r.get("price_egp")) else round(float(r["price_egp"])),
            "sold_marker": bool(SOLD_PATTERN.search(str(r.get("clean_text", "")))),
        })
    return {"fingerprint": fingerprint, "events": events}
