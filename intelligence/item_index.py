"""
Hedonic Item Price Index
Answers: "What is item X worth in the market right now — and is it rising?"

Method (monthly rolling hedonic regression):
  For each month with enough observations, regress log(asking_price) on a
  constant, control features (account level / mythics / guns) and one dummy
  per canonical item. exp(beta_item) is that month's multiplicative premium;
  uplift_egp = median_price_that_month * (exp(beta_item) - 1).

Pure functions over DataFrames.
"""

from typing import Any

import numpy as np
import pandas as pd

MIN_ROWS_PER_MONTH = 40     # regression needs enough listings in the month
MIN_ITEM_FREQ_PER_MONTH = 5 # item must appear this often to be priced

# Controls absorb bundle effects (e.g. glacier-heavy entry-level configs)
# so item coefficients read as marginal premiums vs comparable listings.
_CONTROL_CANDIDATES = [
    "account_level", "mythics_count", "guns_count",
    "xsuits_count", "collection_level", "m4_level", "m4_is_max", "cars_mythic",
]

PRICE_MIN, PRICE_MAX = 1000, 80000


def prepare_priced_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Priced rows only, negotiation-free, with month bucket and item sets."""
    work = df.copy()
    if "posted_at" not in work.columns:
        raise ValueError("item index requires posted_at (use market_data loader)")

    work = work[
        work["price_egp"].notna()
        & work["price_egp"].between(PRICE_MIN, PRICE_MAX)
    ].copy()

    bad_words = (
        r"راسلني|تفاوض|أو أقل|او اقل|قابل للتفاوض|او يزيد|أو يزيد|"
        r"تقريبا|تقريباً|حوالي|يبدأ من|ابتداء من"
    )
    if "clean_text" in work.columns:
        work = work[~work["clean_text"].fillna("").str.contains(bad_words, case=False)]

    items_col = "extracted_items_str"
    if items_col in work.columns:
        items_series = work[items_col].fillna("").astype(str)
    else:
        items_series = pd.Series([""] * len(work), index=work.index)
    work["items"] = items_series.str.split(",").apply(
        lambda lst: [i.strip() for i in lst if i.strip()]
    )
    work["month"] = work["posted_at"].dt.tz_convert("UTC").dt.strftime("%Y-%m")
    return work.reset_index(drop=True)


def _monthly_uplift(month_df: pd.DataFrame, all_items: list[str]) -> dict[str, float]:
    """
    One OLS per month. Returns {item_id: uplift_egp} for items meeting
    frequency thresholds. Robust to singular months via lstsq + rank check.
    """
    n_rows = len(month_df)
    if n_rows < MIN_ROWS_PER_MONTH:
        return {}

    y = np.log(month_df["price_egp"].values.astype(float))

    control_cols = [c for c in _CONTROL_CANDIDATES if c in month_df.columns]
    controls = month_df[control_cols].fillna(0).values.astype(float)

    counts = {
        it: sum(1 for items in month_df["items"] if it in items)
        for it in all_items
    }
    active_items = [it for it in all_items if counts[it] >= MIN_ITEM_FREQ_PER_MONTH]
    if not active_items:
        return {}

    dummies = np.zeros((n_rows, len(active_items)))
    item_sets = [set(items) for items in month_df["items"]]
    for j, it in enumerate(active_items):
        dummies[:, j] = [1.0 if it in s else 0.0 for s in item_sets]

    X = np.column_stack([np.ones(n_rows), controls, dummies])
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)

    median_price = float(month_df["price_egp"].median())
    out = {}
    start = 1 + controls.shape[1]
    for j, it in enumerate(active_items):
        premium_ratio = float(np.exp(beta[start + j]) - 1.0)
        # Cap pathological coefficients (sparse months can explode)
        if -0.95 <= premium_ratio <= 3.0:
            out[it] = round(median_price * premium_ratio)
    return out


def build_item_index(df: pd.DataFrame, min_total_obs: int = 25,
                     recent_months: int = 2) -> dict[str, dict[str, Any]]:
    """
    Full index across months.

    Returns {item_id: {
        current_uplift_egp, previous_uplift_egp, trend ('rising'|'falling'|'stable'),
        series: [{month, uplift_egp}], total_observations, first_month, last_month
    }}
    """
    work = prepare_priced_frame(df)
    all_items = sorted({it for lst in work["items"] for it in lst})

    per_month: dict[str, dict[str, float]] = {}
    obs_counts: dict[str, int] = {it: 0 for it in all_items}
    months_sorted: list[str] = []
    for month, mdf in work.groupby("month"):
        upl = _monthly_uplift(mdf, all_items)
        per_month[month] = upl
        item_sets = mdf["items"].tolist()
        for it in upl:
            obs_counts[it] += sum(1 for s in item_sets if it in s)
        months_sorted.append(month)
    total_priced = len(work)

    # Raw descriptive stats per item (context alongside hedonic coefficients)
    item_of_rows = work[["items", "price_egp"]].explode("items")
    item_medians = item_of_rows.groupby("items")["price_egp"].median().to_dict()

    index: dict[str, dict[str, Any]] = {}
    for it in all_items:
        series = [
            {"month": m, "uplift_egp": per_month[m][it]}
            for m in months_sorted if it in per_month[m]
        ]
        total_obs = obs_counts[it]
        if not series or total_obs < min_total_obs:
            continue

        current = series[-1]["uplift_egp"]
        prev = None
        if len(series) >= recent_months + 1:
            window_prev = series[-(recent_months + 1):-1]
            vals = [s["uplift_egp"] for s in window_prev if s["uplift_egp"] is not None]
            prev = float(np.mean(vals)) if vals else None

        trend = "stable"
        if prev is not None and prev != 0:
            change = (current - prev) / abs(prev)
            trend = "rising" if change > 0.08 else ("falling" if change < -0.08 else "stable")

        index[it] = {
            "current_uplift_egp": current,
            "previous_avg_uplift_egp": round(prev) if prev is not None else None,
            "trend": trend,
            "series": series[-12:],  # last year is plenty for charts
            "total_observations": total_obs,
            "share_of_listings_pct": round(total_obs / max(1, total_priced) * 100, 1),
            "median_price_with_item": int(item_medians[it]) if it in item_medians else None,
            "first_month": series[0]["month"],
            "last_month": series[-1]["month"],
        }
    return index


def get_item_card(index: dict[str, dict[str, Any]], item_id: str) -> dict[str, Any] | None:
    """Convenience single-item view for API consumers."""
    card = index.get(item_id)
    if card is None:
        return None
    return {"item_id": item_id, **card}
