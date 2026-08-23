"""Phase 3 flywheel tests: feedback store, confidence, dataset builder, LLM fallback."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from parser.confidence import estimate_parse_confidence


# ── Confidence estimator ─────────────────────────────────────────────
class TestParseConfidence:
    def test_full_ad_is_high(self):
        parsed = {
            "clean_text": "حساب ببجي لفل 75 ميثك 60 امفور تلجي ماكس السعر 12000",
            "price_egp": 12000.0,
            "m4_type": "glacier",
            "account_level": 75,
            "mythics_count": 60,
            "guns_count": 12,
            "canonical_items": ["glacier_m416"],
            "cars_mythic": 1,
        }
        assert estimate_parse_confidence(parsed) >= 0.95

    def test_empty_is_zero(self):
        assert estimate_parse_confidence({}) == 0.0

    def test_short_text_capped_low(self):
        assert estimate_parse_confidence({"clean_text": "بيع"}) <= 0.2

    def test_partial_ad_midrange(self):
        parsed = {"clean_text": "حساب لفل 80 للبيع بسعر مناسب", "account_level": 80}
        score = estimate_parse_confidence(parsed)
        assert 0.0 < score < 0.5


# ── Feedback store (isolated DB via monkeypatched session) ───────────
@pytest.fixture()
def fb_env(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database.feedback as feedback
    from database.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'fb.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(feedback, "SessionLocal", TestSession)
    return feedback


class TestFeedbackStore:
    def test_save_and_dedupe(self, fb_env):
        ok = fb_env.save_feedback(chat_id=1, message_id=1, label="bought")
        again = fb_env.save_feedback(chat_id=1, message_id=1, label="bought")
        assert ok is True and again is False

    def test_invalid_label_rejected(self, fb_env):
        assert fb_env.save_feedback(chat_id=1, message_id=2, label="nonsense") is False

    def test_same_ad_different_labels_ok(self, fb_env):
        assert fb_env.save_feedback(1, 3, "wrong_parse") is True
        assert fb_env.save_feedback(1, 3, "not_a_deal") is True

    def test_stats_and_verified_sales(self, fb_env):
        # Verified-sales JOIN requires the original ad row to exist
        from database.models import SnipedAd
        Session = fb_env.SessionLocal
        session = Session()
        session.add(SnipedAd(chat_id=1, message_id=11, raw_text="ad",
                             fair_value=5000, segment="s", parsed_data="{}"))
        session.commit()
        session.close()

        fb_env.save_feedback(1, 10, "bought")
        fb_env.save_feedback(1, 11, "sold_price", value_egp=4500.0)
        fb_env.save_feedback(1, 12, "not_a_deal")
        stats = fb_env.get_label_stats()
        assert stats["labels_total"] == 3
        assert stats["verified_sales"] == 2

        sales = fb_env.get_verified_sales()
        assert len(sales) == 1
        assert sales[0]["actual_price"] == 4500.0
        assert sales[0]["raw_text"] == "ad"


# ── Dataset builder ──────────────────────────────────────────────────
class TestDatasetBuilder:
    def test_verified_rows_added_with_weights(self, tmp_path, fb_env, monkeypatch):
        from ml import dataset_builder as dbld
        from ml.pipeline import pipeline_instance

        base = tmp_path / "base.csv"
        base.write_text("clean_text,price_egp\nحساب لفل 70 امفور ماكس السعر 4000,4000\n",
                        encoding="utf-8")

        text = "حساب ببجي لفل 70 ميثك 40 امفور تلجي كيل السعر 3500"
        sale = {"chat_id": 9, "message_id": 99, "raw_text": text,
                "asked_price": 3500.0, "actual_price": 2800.0, "fingerprint": "fp1"}
        monkeypatch.setattr(dbld, "get_verified_sales", lambda: [sale])

        report = dbld.build_training_dataset(base_csv=base,
                                             output_csv=tmp_path / "out.csv")
        assert report["asking_rows"] == 1
        assert report["verified_rows"] == 1

        out = tmp_path / "out.csv"
        import pandas as pd
        df = pd.read_csv(out)
        verified = df[df["label_source"] == "verified"]
        assert len(verified) == 1
        # ground truth replaces the asking price
        assert float(verified.iloc[0]["price_egp"]) == pytest.approx(2800.0)
        assert float(verified.iloc[0]["sample_weight"]) == dbld.VERIFIED_WEIGHT
        assert float(df[df.label_source == "asking"].iloc[0]["sample_weight"]) == 1.0
        # sanity: pipeline actually parsed something
        features = pipeline_instance.process(text)
        assert features.get("price_egp") is not None


# ── LLM fallback merge logic ─────────────────────────────────────────
class TestLLMFallback:
    def _with_env(self, monkeypatch, tmp_path, enabled=True, key="test"):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "1" if enabled else "0")
        monkeypatch.setenv("OPENAI_API_KEY", key)
        from parser import llm_fallback as llm
        monkeypatch.setattr(llm, "LOG_PATH", tmp_path / "llm_fallback.jsonl")
        return llm

    def test_disabled_leaves_untouched(self, monkeypatch, tmp_path):
        llm = self._with_env(monkeypatch, tmp_path, enabled=False)
        parsed = {"price_egp": 100}
        out = llm.maybe_llm_augment(dict(parsed), "نص", 0.1)
        assert out["price_egp"] == 100 and "llm_augmented" not in out

    def test_high_confidence_skips_llm(self, monkeypatch, tmp_path):
        llm = self._with_env(monkeypatch, tmp_path)
        called = {"n": 0}

        def fake_call(prompt):
            called["n"] += 1
            return {}

        monkeypatch.setattr(llm, "_call_llm", fake_call)
        out = llm.maybe_llm_augment({}, "نص", 0.9)
        assert called["n"] == 0
        assert "llm_augmented" not in out

    def test_fills_missing_never_overrides(self, monkeypatch, tmp_path):
        llm = self._with_env(monkeypatch, tmp_path)

        def fake_call(prompt):
            return {"account_level": 77, "mythics_count": 999, "items": ["glacier_m416"]}

        monkeypatch.setattr(llm, "_call_llm", fake_call)
        parsed = {
            "mythics_count": 42,  # already known — must NOT be overridden
            "canonical_items": [],
        }
        out = llm.maybe_llm_augment(parsed, "نص غامض", 0.2)
        assert out["account_level"] == 77          # filled missing field
        assert out["mythics_count"] == 42          # preserved
        assert "glacier_m416" in out["canonical_items"]
        assert out["llm_augmented"] is True
        # disagreement logged
        log_file = tmp_path / "llm_fallback.jsonl"
        assert log_file.exists()
        events = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
        assert events[-1]["event"] == "augment"

    def test_llm_failure_is_silent(self, monkeypatch, tmp_path):
        llm = self._with_env(monkeypatch, tmp_path)

        def boom(prompt):
            raise RuntimeError("network down")

        monkeypatch.setattr(llm, "_call_llm", boom)
        parsed = {"mythics_count": 5}
        out = llm.maybe_llm_augment(parsed, "نص", 0.1)
        assert out["mythics_count"] == 5
