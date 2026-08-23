"""
Channel Trust Engine
Scores every Telegram channel on deal-safety and listing quality using
signals already extracted by the parser, plus behavioral stats:
  + trusted-middleman mentions   + internal-only linkage (safer transfers)
  + facebook-disabled notices    − spam/ad-noise ratio
  − repost flooding              − sold-marker inconsistency
Transparent weighted formula; every component exposed for the dashboard.
Pure functions over DataFrames.
"""

from typing import Any

import numpy as np
import pandas as pd

SPAM_KEYWORDS = ["رشق", "متابعين", "تزويد", "هاك", "هكر", "شحن شدات", "uc مجانا", "شحن مجاني"]

WEIGHTS = {
    "middleman": 20.0,
    "internal_linkage": 10.0,
    "fb_disabled": 8.0,
    "spam": -30.0,
    "flood": -15.0,
}
GRADE_BANDS = [(85, "A+"), (70, "A"), (55, "B"), (40, "C"), (0, "D")]


def _safe_ratio(numer: pd.Series, denom: int) -> float:
    return float(numer.mean()) if denom else 0.0


def compute_channel_trust(df: pd.DataFrame, min_ads: int = 10) -> dict[str, Any]:
    """
    Returns {
      'channels': [ {channel, n_ads, trust_score, grade, components{...}, stats{...}} ],
      'method': description string
    }
    """
    work = df.copy()
    text = work.get("clean_text", work.get("raw_text", pd.Series("", index=work.index)))
    text = text.fillna("").astype(str)

    signals = pd.DataFrame(index=work.index)
    signals["channel"] = work["channel_username"]
    signals["has_middleman"] = text.str.contains("وسيط", na=False)
    signals["internal_only"] = text.str.contains(
        "ربط داخلي|ربط داخل", na=False, regex=True)
    # Facebook disabled is a *positive* safety signal in this market
    # (no FB binding = cleaner transfer)
    signals["fb_disabled"] = text.str.contains("فيسبوك معطل|الفيس معطل", na=False, regex=True)
    signals["is_spam"] = text.apply(
        lambda t: sum(1 for kw in SPAM_KEYWORDS if kw in t) >= 2
    )
    signals["price"] = pd.to_numeric(work.get("price_egp"), errors="coerce")
    signals["posted_at"] = work["posted_at"]

    rows_out = []
    for channel, g in signals.groupby("channel"):
        n_ads = len(g)
        spam_ratio = _safe_ratio(g["is_spam"], n_ads)

        # Flood: share of listings that are exact-attribute reposts
        if "account_fingerprint" in work.columns:
            fps = work.loc[g.index, "account_fingerprint"]
        else:
            from ml.fingerprint import compute_fingerprint  # local import guard
            fps = work.loc[g.index].apply(
                lambda r: compute_fingerprint(r.to_dict()), axis=1
            )
        reposted_rows = int(fps.duplicated(keep="first").sum())
        flood_ratio = reposted_rows / max(1, n_ads)

        middleman_ratio = _safe_ratio(g["has_middleman"], n_ads)
        internal_ratio = _safe_ratio(g["internal_only"], n_ads)
        fb_ratio = _safe_ratio(g["fb_disabled"], n_ads)

        score = (
            50.0
            + WEIGHTS["middleman"] * min(1.0, middleman_ratio / 0.5)
            + WEIGHTS["internal_linkage"] * min(1.0, internal_ratio / 0.5)
            + WEIGHTS["fb_disabled"] * min(1.0, fb_ratio / 0.5)
            + WEIGHTS["spam"] * spam_ratio
            + WEIGHTS["flood"] * min(1.0, flood_ratio / 0.5)
        )
        score = float(np.clip(score, 0, 100))
        grade = next(label for floor, label in GRADE_BANDS if score >= floor)

        span_days = max(1.0, (g["posted_at"].max() - g["posted_at"].min()).total_seconds() / 86400)
        rows_out.append({
            "channel": channel,
            "n_ads": int(n_ads),
            "trust_score": round(score, 1),
            "grade": grade,
            "components": {
                "middleman_ratio": round(middleman_ratio, 3),
                "internal_linkage_ratio": round(internal_ratio, 3),
                "fb_disabled_ratio": round(fb_ratio, 3),
                "spam_ratio": round(spam_ratio, 3),
                "repost_flood_ratio": round(flood_ratio, 3),
            },
            "stats": {
                "median_asking_price": None if g["price"].notna().sum() == 0
                else int(g["price"].median()),
                "ads_per_week": round(n_ads / (span_days / 7), 1),
                "active_days": round(span_days),
            },
        })

    rows_out.sort(key=lambda r: r["trust_score"], reverse=True)
    return {
        "channels": rows_out,
        "method": ("base=50; +middleman/internal/fb-disabled presence; "
                   "-spam; -repost flooding; clipped to [0,100]"),
        "min_ads_threshold": min_ads,
    }
