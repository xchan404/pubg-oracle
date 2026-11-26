"""
Week 1 data-quality tests:
  - redundant "الف" price typos (the 145M bug)
  - plausibility bounds
  - freshness monitoring
  - composite (channel, message_id) join regression
"""

import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from parser.regex_parser import extract_prices


class TestPriceTypos:
    @pytest.mark.parametrize("text,expected", [
        # The exact production outliers
        ("السعر : 145000 الف ج - 2700 د", (145000.0, None)),
        ("السعر : 84500 الف ج - 1800 USDT", (84500.0, 1800.0)),
        # Normal thousand notation still works
        ("السعر: 15 الف جنيه", (15000.0, None)),
        ("السعر: 1.5k", (1500.0, None)),
        ("السعر: 500k", (500000.0, None)),
        # Plain EGP
        ("السعر: 12500 ج", (12500.0, None)),
        ("السعر: 3500 جنيه", (3500.0, None)),
        ("السعر: 800000 ج", (800000.0, None)),
        # USD forms
        ("price $150", (None, 150.0)),
        # Implausible values are rejected, not silently trained on
        ("السعر: 145000000 ج", (None, None)),
        ("السعر: 3000000 ج", (None, None)),
        ("السعر: 50 ج", (None, None)),
        # Popularity points are not prices
        ("الشعبيه 700k الانجازات كامل", (None, None)),
        ("- شعبيه ( 655k )", (None, None)),
        ("ميثك40_شعبيه 650الف _ليفل78", (None, None)),
        ("الشعبيه { 530k}", (None, None)),
        ("60 مليون شعبيه", (None, None)),
        # ...but a real price elsewhere in the same ad still wins
        ("شعبيه 650الف\nالسعر : 1300\nنزل ل 1100", (1300.0, None)),
        ("شعبيه (600K)\nسعر : 4500", (4500.0, None)),
    ])
    def test_extract_prices(self, text, expected):
        assert extract_prices(text) == expected

    def test_redundant_suffix_does_not_multiply(self):
        # 84,500 must never become 84,500,000
        egp, _ = extract_prices("السعر: 84500 الف ج")
        assert egp == 84500.0
        assert egp < 1_000_000

    def test_popularity_never_becomes_price(self):
        """
        Popularity ("شعبيه 650k") lives in the same numeric range as account
        prices and produced 15 fake 500k+ EGP listings at the top of the
        market index.
        """
        for text in (
            "الشعبيه 700k",
            "شعبيه (655k)",
            "شعبيه 650 الف",
            "60 مليون شعبيه",
            "مطلوب شعبيه متفرقات\nبخلص اي كميه مطلوب 600k",
        ):
            egp, _ = extract_prices(text)
            assert egp is None, f"popularity leaked into price: {text!r} -> {egp}"

    def test_buyer_request_is_not_a_listing_price(self):
        # "مطلوب شعبيه ... مطلوب 600k" is someone buying popularity, not a listing
        assert extract_prices("مطلوب شعبيه متفرقات\nمطلوب 600k") == (None, None)


def _make_listings_db(path, rows):
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE raw_messages ("
            "channel_username TEXT, message_id INTEGER, date TEXT, text TEXT)"
        )
        conn.executemany(
            "INSERT INTO raw_messages (channel_username, message_id, date, text) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


class TestFreshness:
    def test_missing_db(self, tmp_path):
        from intelligence.freshness import get_freshness

        out = get_freshness(tmp_path / "nope.db")
        assert out["status"] == "missing"
        assert out["is_stale"] is True

    def test_empty_db(self, tmp_path):
        from intelligence.freshness import get_freshness

        db = tmp_path / "empty.db"
        _make_listings_db(db, [])
        out = get_freshness(db)
        assert out["status"] == "empty"
        assert out["listings_total"] == 0

    def test_fresh_db(self, tmp_path):
        from intelligence.freshness import get_freshness

        db = tmp_path / "fresh.db"
        now = datetime.now(UTC)
        _make_listings_db(db, [
            ("chan_a", 1, (now - timedelta(hours=1)).isoformat(), "x"),
            ("chan_b", 2, (now - timedelta(hours=2)).isoformat(), "y"),
        ])
        out = get_freshness(db)
        assert out["status"] == "fresh"
        assert out["is_stale"] is False
        assert out["listings_24h"] == 2
        assert out["channels_24h"] == 2
        assert out["hours_since_last"] < 2

    def test_stale_db(self, tmp_path):
        from intelligence.freshness import get_freshness

        db = tmp_path / "stale.db"
        old = datetime.now(UTC) - timedelta(days=5)
        _make_listings_db(db, [("chan_a", 1, old.isoformat(), "x")])
        out = get_freshness(db)
        assert out["status"] == "stale"
        assert out["is_stale"] is True
        assert out["listings_24h"] == 0
        assert out["listings_7d"] == 1
        assert out["hours_since_last"] > 100


class TestCompositeKey:
    def test_same_message_id_in_two_channels_stays_two_rows(self, tmp_path):
        """
        Regression: joining parsed_accounts to raw_messages on message_id
        alone inflates every per-channel statistic. The production join must
        use (channel_username, message_id).
        """
        from intelligence.market_data import _load_db_enrichment

        db = tmp_path / "composite.db"
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "CREATE TABLE raw_messages ("
                "channel_username TEXT, message_id INTEGER, date TEXT, text TEXT)"
            )
            conn.execute(
                "CREATE TABLE parsed_accounts ("
                "channel_username TEXT, message_id INTEGER, extracted_items_str TEXT)"
            )
            conn.executemany(
                "INSERT INTO raw_messages VALUES (?, ?, ?, ?)",
                [
                    ("chan_a", 100, "2026-01-01T00:00:00+00:00", "a"),
                    ("chan_b", 100, "2026-01-02T00:00:00+00:00", "b"),
                ],
            )
            conn.executemany(
                "INSERT INTO parsed_accounts VALUES (?, ?, ?)",
                [("chan_a", 100, "m4"), ("chan_b", 100, "mummy")],
            )
            conn.commit()
        finally:
            conn.close()

        df = _load_db_enrichment(db)
        assert len(df) == 2
        assert set(df["channel_username"]) == {"chan_a", "chan_b"}
        assert set(df["extracted_items_str"]) == {"m4", "mummy"}
