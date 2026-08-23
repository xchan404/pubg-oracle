"""Phase 2 intelligence engine tests (synthetic DataFrames, no DB access)."""

import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from intelligence.item_index import build_item_index
from intelligence.repost_engine import (
    build_clusters,
    detect_sold_markers,
    get_listing_timeline,
    get_repost_summary,
)
from intelligence.trust import compute_channel_trust

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def make_rows(n, fingerprint, channel="chan_a", price=5000, days=0, text="حساب للبيع",
              **extra):
    row = {
        "channel_username": channel,
        "message_id": n,
        "price_egp": price,
        "posted_at": T0 + timedelta(days=days),
        "clean_text": text,
        "extracted_items_str": extra.pop("items", "glacier_m416"),
        "account_level": 70,
        "mythics_count": 40,
        "guns_count": 10,
        **({"account_fingerprint": fingerprint} if fingerprint else {}),
        **extra,
    }
    return row


def base_df():
    rows = [
        make_rows(1, "fp_same", price=5000, days=0),
        make_rows(2, "fp_same", channel="chan_b", price=4800, days=3),
        make_rows(3, "fp_other", price=9000, days=1),
    ]
    return pd.DataFrame(rows)


class TestRepostEngine:
    def test_clusters_group_reposts(self):
        clusters = build_clusters(base_df())
        same = clusters[clusters["account_fingerprint"] == "fp_same"].iloc[0]
        assert same["n_posts"] == 2
        assert same["channels"] == ["chan_a", "chan_b"]
        assert same["days_on_market"] == 3.0

    def test_sold_marker_detection(self):
        df = detect_sold_markers(pd.DataFrame([
            {"clean_text": "تم البيع الحمد لله"},
            {"clean_text": "حساب متاح للبيع"},
            {"clean_text": None},
        ]))
        assert list(df["is_sold_marker"]) == [True, False, False]

    def test_summary_counts(self):
        s = get_repost_summary(base_df())
        assert s["total_listings"] == 3
        assert s["unique_accounts"] == 2
        assert s["reposted_accounts"] == 1
        top = s["top_reposts"][0]
        assert top["fingerprint"] == "fp_same"
        assert top["still_listed"] is True

    def test_timeline_unknown_fp(self):
        assert "error" in get_listing_timeline(base_df(), "nope")

    def test_price_collision_cluster_dropped(self):
        # Same fp but wildly different prices -> treated as accidental collision
        df = pd.DataFrame([
            make_rows(1, "fp_x", price=2000, days=0),
            make_rows(2, "fp_x", price=40000, days=5),
            make_rows(3, None, price=3000, days=6),  # no fp column value
        ])
        clusters = build_clusters(df)
        assert "fp_x" not in clusters["account_fingerprint"].values


class TestItemIndex:
    def _synthetic_market(self):
        rng = np.random.default_rng(7)
        rows = []
        mid = 0
        for month in range(6):
            for i in range(60):
                has_item = i % 2 == 0
                premium = 3000 if has_item else 0.0
                price = 6000 + premium + rng.normal(0, 400)
                rows.append({
                    "channel_username": "c",
                    "message_id": mid,
                    "price_egp": max(1000.0, float(price)),
                    "posted_at": T0 + pd.DateOffset(months=month) + timedelta(hours=i % 20),
                    "clean_text": "ad",
                    # NOTE: controls are independent of item presence —
                    # otherwise OLS splits the premium across collinear columns
                    "extracted_items_str": "test_item" if has_item else "",
                    "account_level": int(rng.integers(50, 85)),
                    "mythics_count": int(rng.integers(20, 80)),
                    "guns_count": int(rng.integers(5, 25)),
                    "m4_level": int(rng.integers(1, 8)),
                })
                mid += 1
        return pd.DataFrame(rows)

    def test_recovers_planted_premium(self):
        idx = build_item_index(self._synthetic_market())
        assert "test_item" in idx
        card = idx["test_item"]
        # planted ~+3000 EGP on a ~6k base => uplift should be clearly positive
        assert card["current_uplift_egp"] > 800

    def test_rare_item_excluded(self):
        df = self._synthetic_market()
        df.loc[df.index[:3], "extracted_items_str"] = "ultra_rare"
        idx = build_item_index(df)
        assert "ultra_rare" not in idx


class TestChannelTrust:
    def test_trusted_channel_beats_spammy(self):
        good = [make_rows(i, f"g{i}", channel="good", text="وسيط ربط داخلي حساب")
                for i in range(12)]
        bad = [make_rows(100 + i, f"b{i}", channel="spammy",
                         text="رشق متابعين هاك شحن شدات") for i in range(12)]
        result = compute_channel_trust(pd.DataFrame(good + bad))
        by_channel = {c["channel"]: c for c in result["channels"]}
        assert by_channel["good"]["trust_score"] > by_channel["spammy"]["trust_score"]
        assert by_channel["good"]["grade"] in ("A+", "A")
        assert by_channel["spammy"]["grade"] in ("C", "D")

    def test_components_exposed(self):
        df = pd.DataFrame([make_rows(i, f"f{i}", channel="one") for i in range(10)])
        out = compute_channel_trust(df)
        comp = out["channels"][0]["components"]
        assert set(comp) >= {"middleman_ratio", "spam_ratio", "repost_flood_ratio"}
