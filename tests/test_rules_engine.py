"""Tests for the declarative pricing rules engine."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from ml.rules_engine import PricingRulesEngine, build_context


@pytest.fixture(scope="module")
def engine():
    return PricingRulesEngine()


class TestBuildContext:
    def test_has_m4_by_level(self):
        assert build_context({"m4_level": 7}, "", {}).get("_has_m4") is True

    def test_has_m4_absent(self):
        assert build_context({"mythics_count": 50}, "", {}).get("_has_m4") is False

    def test_m4_type_zero_string_is_not_m4(self):
        assert build_context({"m4_type": "0"}, "", {}).get("_has_m4") is False

    def test_mythic_car_by_count_and_flag(self):
        assert build_context({"cars_mythic": 2}, "", {}).get("_has_mythic_car") is True
        assert build_context({"has_car_dodge": 1}, "", {}).get("_has_mythic_car") is True

    def test_m4_level_eff_defaults_to_1(self):
        assert build_context({}, "", {}).get("m4_level_eff") == 1

    def test_m4_max_tier_from_flag_or_level(self):
        assert build_context({"m4_is_max": 1}, "", {}).get("_m4_is_max_tier") is True
        assert build_context({"m4_level": 7}, "", {}).get("_m4_is_max_tier") is True
        assert build_context({"m4_level": 5}, "", {}).get("_m4_is_max_tier") is False


class TestRarePremiums:
    def test_joker_locked_flag(self, engine):
        ctx = build_context({"has_joker_fox": 1, "has_joker_fox_locked": 1}, "", {})
        assert engine.compute_rare_premium(ctx) == 1500.0

    def test_joker_locked_regex_fallback(self, engine):
        ctx = build_context({"has_joker_fox": 1}, "جوكر فوكس مقفول", {})
        assert engine.compute_rare_premium(ctx) == 1500.0

    def test_open_joker_no_premium(self, engine):
        ctx = build_context({"has_joker_fox": 1}, "جوكر فوكس مفتوح", {})
        assert engine.compute_rare_premium(ctx) == 0.0

    def test_mummy_helmet(self, engine):
        ctx = build_context({"has_mummy_helmet": 1}, "", {})
        assert engine.compute_rare_premium(ctx) == 1500.0

    def test_xsuit_upgrade_fires_once(self, engine):
        # Both upgrade regexes match; legacy if/elif semantics => single 1500
        ctx = build_context(
            {"has_xsuit": 1},
            "بدلة فرعون ماكس كيل",
            {},
        )
        premium = engine.compute_rare_premium(ctx)
        assert premium >= 1500.0

    def test_old_season_avatar(self, engine):
        ctx = build_context({}, "فيه حاصد موسم التاني", {})
        assert engine.compute_rare_premium(ctx) == 1500.0

    def test_mythic_cars_formula(self, engine):
        # base 1500 + (3-1)*1000 = 3500
        ctx = build_context({"cars_mythic": 3}, "", {})
        assert engine.compute_rare_premium(ctx) == 3500.0

    def test_re2_frame_wording(self, engine):
        ctx = build_context({}, "فيه اطار RE2 جودزيلا", {})
        assert engine.compute_rare_premium(ctx) == 300.0


class TestStatPremiums:
    def test_m4_level_tiers_first_match(self, engine):
        # level 4 + max flag: legacy first branch wins (+500 only)
        ctx = build_context({"m4_level": 4, "m4_is_max": 1}, "", {})
        assert engine.compute_stat_premium(ctx) == 500.0

    def test_m4_high_lvl_no_max(self, engine):
        ctx = build_context({"m4_level": 6, "m4_is_max": 0}, "", {})
        assert engine.compute_stat_premium(ctx) == 800.0

    def test_m4_max_only(self, engine):
        ctx = build_context({"m4_level": 7, "m4_is_max": 1}, "", {})
        assert engine.compute_stat_premium(ctx) == 1500.0

    def test_mythics_ladder_first_match(self, engine):
        ctx = build_context({"mythics_count": 120}, "", {})
        assert engine.compute_stat_premium(ctx) == 1000.0

    def test_guns_ladder_first_match(self, engine):
        ctx = build_context({"guns_count": 35}, "", {})
        assert engine.compute_stat_premium(ctx) == 1500.0

    def test_absent_columns_no_crash_no_premium(self, engine):
        ctx = build_context({}, "", {})
        assert engine.compute_stat_premium(ctx) == 0.0


class TestCaps:
    def test_no_anchors_cap(self, engine):
        ctx = build_context({}, "", {})
        out = engine.apply_cap(ctx, fair_value=5000.0, extra_premium=0.0, final_price=5000.0)
        assert out["fair_value"] == 500
        assert out["segment"] == "Capped: No Anchors (Dynamic)"

    def test_ultra_rares_branch(self, engine):
        ctx = build_context({}, "", {})
        out = engine.apply_cap(ctx, fair_value=90000.0, extra_premium=3000.0, final_price=90000.0)
        assert out["fair_value"] == 6500  # 3500 + 3000

    def test_with_m4_max(self, engine):
        ctx = build_context({"m4_level": 8, "m4_is_max": 1}, "", {})
        out = engine.apply_cap(ctx, fair_value=90000.0, extra_premium=1000.0, final_price=90000.0)
        assert out["fair_value"] == 6000  # 5000 + 1000
        assert "Max M4" in out["segment"]

    def test_fixed_cap_joker_mummy(self, engine):
        ctx = build_context({"has_mummy": 1}, "", {})
        out = engine.apply_cap(ctx, fair_value=9000.0, extra_premium=0.0, final_price=9000.0)
        assert out["fair_value"] == 2000  # fixed, extra NOT added


class TestBlendAndFlipping:
    def test_blend_cheap(self, engine):
        blend = engine.select_blend(14999.0)
        assert blend["weights"]["lightgbm"] == 0.6
        assert "<15k" in blend["segment"]

    def test_blend_expensive(self, engine):
        blend = engine.select_blend(15000.0)
        assert blend["weights"]["xgboost"] == 0.7

    def test_flipping_tier_boundaries(self, engine):
        cheap = engine.compute_flipping_advice(2999.0, asking_price=1000.0)
        mid = engine.compute_flipping_advice(3000.0, asking_price=1000.0)
        whale = engine.compute_flipping_advice(15001.0, asking_price=1000.0)
        assert abs((cheap["target_buy_price"] / 2999.0) - 0.70) < 0.02
        assert abs((mid["target_buy_price"] / 3000.0) - 0.80) < 0.02
        assert abs((whale["target_sell_price"] / 15001.0) - 1.10) < 0.02

    def test_ratings(self, engine):
        assert "اشترِ فوراً" in engine.compute_flipping_advice(5000.0, 1000.0)["deal_rating"]
        assert "عادل" in engine.compute_flipping_advice(5000.0, 4500.0)["deal_rating"]
        assert "غالي" in engine.compute_flipping_advice(5000.0, 9000.0)["deal_rating"]


class TestConfidence:
    def test_clamped_range(self, engine):
        for features in ({}, {"has_mummy": 1, "has_xsuit": 1, "cars_mythic": 9}):
            conf = engine.compute_confidence(build_context(features, "", {}), 999999.0)
            score = int(conf["score"].rstrip("%"))
            assert 40 <= score <= 99

    def test_high_confidence_label_for_simple_case(self, engine):
        conf = engine.compute_confidence(build_context({}, "", {}), 2000.0)
        assert "95%" in conf["score"]
