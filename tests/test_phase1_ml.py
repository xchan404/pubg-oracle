"""Phase 1 ML infrastructure tests: fingerprinting, text cleaner, training utils."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.fingerprint import compute_fingerprint, text_jaccard
from ml.train import blended_price, monotone_vector
from parser.text_cleaner import clean_text, strip_diacritics

BASE_ATTRS = {
    "account_level": 75,
    "mythics_count": 60,
    "guns_count": 12,
    "xsuits_count": 2,
    "m4_type": "glacier",
    "m4_level": 7,
    "m4_is_max": 1,
}


class TestFingerprint:
    def test_stable_across_channels(self):
        """Same account reposted on different channels must collide."""
        from_channel_a = {**BASE_ATTRS, "channel_username": "chan_a", "message_id": 1}
        from_channel_b = {**BASE_ATTRS, "channel_username": "chan_b", "message_id": 999}
        assert compute_fingerprint(from_channel_a) == compute_fingerprint(from_channel_b)

    def test_differs_on_core_attribute(self):
        assert compute_fingerprint(BASE_ATTRS) != compute_fingerprint({**BASE_ATTRS, "m4_level": 6})

    def test_type_tolerance(self):
        int_row = {**BASE_ATTRS, "account_level": 75}
        float_row = {**BASE_ATTRS, "account_level": 75.0}
        str_row = {**BASE_ATTRS, "account_level": "75"}
        assert (compute_fingerprint(int_row)
                == compute_fingerprint(float_row)
                == compute_fingerprint(str_row))

    def test_items_signature_included(self):
        with_items = {**BASE_ATTRS, "canonical_items": ["glacier_m416", "face_girl"]}
        with_items_reordered = {**BASE_ATTRS, "canonical_items": ["face_girl", "glacier_m416"]}
        no_items = dict(BASE_ATTRS)
        assert compute_fingerprint(with_items) == compute_fingerprint(with_items_reordered)
        assert compute_fingerprint(with_items) != compute_fingerprint(no_items)

    def test_loose_tolerates_small_drift(self):
        strict_a = compute_fingerprint(BASE_ATTRS)
        strict_b = compute_fingerprint({**BASE_ATTRS, "account_level": 74})
        loose_a = compute_fingerprint(BASE_ATTRS, loose=True)
        loose_b = compute_fingerprint({**BASE_ATTRS, "account_level": 74}, loose=True)
        assert strict_a != strict_b          # strict is exact
        assert loose_a == loose_b            # loose absorbs ±few levels

    def test_jaccard(self):
        assert text_jaccard("حساب لفل 75 امفور تلجي", "امفور تلجي حساب لفل 75") > 0.9
        assert text_jaccard("حساب لفل 75", "سيارة مكلارين للبيع") < 0.3


class TestTextCleanerDiacritics:
    def test_strip_diacritics_and_tatweel(self):
        assert strip_diacritics("حســابٌ للّبِيــع") == "حساب للبيع"

    def test_clean_text_normalizes_diacritics_end_to_end(self):
        # Diacritized price line must still parse identically after cleaning
        plain = clean_text("السعر 5000")
        decorated = clean_text("السَّعْرُ 5000")
        assert plain == decorated


class TestTrainingUtils:
    def test_monotone_vector_directions(self):
        vec = dict(zip(
            ("mythics_count", "has_mummy", "tfidf_3", "cluster_2", "guns_per_mythic_ratio"),
            monotone_vector(["mythics_count", "has_mummy", "tfidf_3", "cluster_2",
                             "guns_per_mythic_ratio"]),
            strict=True,
        ))
        assert vec["mythics_count"] == 1
        assert vec["has_mummy"] == 1
        assert vec["tfidf_3"] == 0
        assert vec["cluster_2"] == 0
        assert vec["guns_per_mythic_ratio"] == 0

    def test_blended_price_segments(self):
        import numpy as np
        out = blended_price(
            np.array([30000.0]), np.array([10000.0]), np.array([9000.0])
        )
        assert abs(out[0] - (10000 * 0.6 + 9000 * 0.4)) < 1e-6  # cheap blend
        out_whale = blended_price(
            np.array([20000.0]), np.array([16000.0]), np.array([15000.0])
        )
        assert abs(out_whale[0] - (20000 * 0.7 + 15000 * 0.3)) < 1e-6  # whale blend
