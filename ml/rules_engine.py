"""
PUBG Market Intelligence — Declarative Pricing Rules Engine
Loads config/pricing_rules.yaml and applies business-rule premiums,
caps, multi-M4 adjustments, confidence scoring, and flipping margins.

Extracted from ml/predict.py (Phase 0). Behavior-preserving by design:
every threshold/amount mirrors the legacy hard-coded logic exactly.
"""

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES_PATH = Path(os.getenv("PRICING_RULES_PATH",
                                     str(Path(__file__).resolve().parent.parent / "config" / "pricing_rules.yaml")))

REQUIRED_RULE_KEYS = ("rare_premiums", "stat_premiums", "caps", "confidence", "blend", "flipping")


def validate_rules_text(text: str) -> tuple[dict, list[str]]:
    """
    Parses candidate pricing-rules YAML and returns (rules, errors).
    Empty errors means the text is structurally acceptable for hot-reload.
    """
    errors: list[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return {}, [f"YAML parse error: {e}"]
    if not isinstance(data, dict):
        return {}, ["Top level must be a mapping"]
    for key in REQUIRED_RULE_KEYS:
        if key not in data:
            errors.append(f"Missing required section: {key}")
    caps = data.get("caps") or {}
    if isinstance(caps, dict):
        if "no_m4" not in caps or "with_m4" not in caps:
            errors.append("caps must contain 'no_m4' and 'with_m4' groups")
        else:
            for group in ("no_m4", "with_m4"):
                if not isinstance(caps.get(group), list) or not caps.get(group):
                    errors.append(f"caps.{group} must be a non-empty list")
    blend = data.get("blend") or {}
    if isinstance(blend, dict):
        for seg in ("cheap", "expensive"):
            b = blend.get(seg)
            if not isinstance(b, dict) or "weights" not in b or "segment" not in b:
                errors.append(f"blend.{seg} requires weights + segment")
    conf = data.get("confidence") or {}
    if isinstance(conf, dict) and "labels" not in conf:
        errors.append("confidence.labels missing")
    flip = data.get("flipping") or {}
    if isinstance(flip, dict) and "tiers" not in flip:
        errors.append("flipping.tiers missing")
    return data, errors


# ─────────────────────────────────────────────────────────────────────
# Rule context: exposes features + derived anchors to conditions
# ─────────────────────────────────────────────────────────────────────
@dataclass
class RuleContext:
    features: dict[str, Any]
    text: str = ""
    account_data: dict[str, Any] = field(default_factory=dict)
    _derived: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        if name in self._derived:
            return self._derived[name]
        return self.features.get(name, default)


def _num(value: Any) -> float | None:
    """None-safe numeric coercion (NaN -> None)."""
    try:
        import math
        if value is None:
            return None
        f = float(value)
        if math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def build_context(features: dict[str, Any], text: str, account_data: dict[str, Any]) -> RuleContext:
    """
    Recreates the exact anchor-detection block from legacy predict():
    has_m4 / has_xsuit / has_joker_fox / has_mummy / has_mummy_helmet /
    has_mythic_car / has_girl_face / m4_level_eff / m4_is_max_tier.
    """
    f = features

    def col_eq1(name: str) -> bool:
        return name in f and f.get(name) == 1

    # --- has_m4 detection (legacy semantics) ---
    has_m4_type = "m4_type" in f and f.get("m4_type") not in [None, 0, "0"]
    m4_lvl_raw = _num(f.get("m4_level"))
    has_m4_level = m4_lvl_raw is not None and m4_lvl_raw > 0
    has_m4_max_flag = col_eq1("m4_is_max")
    has_m4 = has_m4_type or has_m4_level or has_m4_max_flag

    cars_mythic = _num(f.get("cars_mythic"))
    has_mythic_car = False
    if cars_mythic is not None and cars_mythic > 0:
        has_mythic_car = True
    if col_eq1("has_car_mclaren") or col_eq1("has_car_dodge"):
        has_mythic_car = True
    rare_str = str(f.get("rare_items_str", "")) if f.get("rare_items_str") is not None else ""
    if "car_" in rare_str and "car_dev_fleet" not in rare_str:
        has_mythic_car = True

    # Effective M4 level for caps (legacy default = 1)
    m4_level_eff = int(m4_lvl_raw) if m4_lvl_raw is not None else 1
    m4_is_max_tier = has_m4_max_flag or m4_level_eff >= 7

    derived = {
        "_has_m4": has_m4,
        "_has_m4_type": has_m4_type,
        "_has_joker_fox": col_eq1("has_joker_fox"),
        "_has_mummy": col_eq1("has_mummy"),
        "_has_mummy_helmet": col_eq1("has_mummy_helmet"),
        "_has_xsuit": col_eq1("has_xsuit"),
        "_has_girl_face": col_eq1("has_face_girl"),
        "_has_mythic_car": has_mythic_car,
        "_cars_mythic_count": int(cars_mythic) if cars_mythic is not None else 0,
        "_m4_is_max": has_m4_max_flag,
        "_m4_is_max_tier": m4_is_max_tier,
        "m4_level_eff": m4_level_eff,
        "m4_level_raw": int(m4_lvl_raw) if m4_lvl_raw is not None else None,
    }
    return RuleContext(features=f, text=text or "", account_data=account_data, _derived=derived)


# ─────────────────────────────────────────────────────────────────────
# Condition evaluation
# ─────────────────────────────────────────────────────────────────────
def _cmp(left: Any, op: str, right: Any) -> bool:
    if op == "truthy":
        return bool(left)
    if op == "not_null":
        return left is not None
    ln, rn = _num(left), _num(right)
    if op == "eq":
        return ln is not None and rn is not None and left == right
    if op == "neq":
        return left != right
    if ln is None or rn is None:
        return False
    if op == "gt":
        return ln > rn
    if op == "gte":
        return ln >= rn
    if op == "lt":
        return ln < rn
    if op == "lte":
        return ln <= rn
    raise ValueError(f"Unknown operator: {op}")


def eval_condition(cond: dict[str, Any], ctx: RuleContext, extra: dict[str, Any] | None = None) -> bool:
    """Evaluates a declarative condition dict against the context."""
    extra = extra or {}

    def lookup(name: str) -> Any:
        if name in extra:
            return extra[name]
        return ctx.get(name)

    if cond.get("always"):
        return True
    if "all_of" in cond:
        return all(eval_condition(c, ctx, extra) for c in cond["all_of"])
    if "any_of" in cond:
        return any(eval_condition(c, ctx, extra) for c in cond["any_of"])
    if "not" in cond:
        return not eval_condition(cond["not"], ctx, extra)
    if "feature" in cond:
        spec = cond["feature"]
        name = spec["name"]
        known = name in ctx.features or name in ctx._derived or name in extra
        if spec.get("must_exist") and not known:
            return False
        return _cmp(lookup(name), spec["op"], spec.get("value"))
    if "regex" in cond:
        spec = cond["regex"]
        flags = 0
        flag_name = str(spec.get("flags", "") or "")
        if "IGNORECASE" in flag_name:
            flags |= re.IGNORECASE
        return re.search(spec["pattern"], ctx.text, flags) is not None
    if "value_name" in cond:  # confidence penalties compare named runtime values
        return _cmp(extra.get(cond["value_name"]), cond["op"], cond.get("value"))
    raise ValueError(f"Unknown condition spec: {cond}")


# ─────────────────────────────────────────────────────────────────────
# The engine
# ─────────────────────────────────────────────────────────────────────
class PricingRulesEngine:
    def __init__(self, rules_path: str | None = None):
        path = Path(rules_path) if rules_path else DEFAULT_RULES_PATH
        with open(path, encoding="utf-8") as fh:
            self.rules = yaml.safe_load(fh)
        self.version = self.rules.get("version", 1)

    # ── premiums ────────────────────────────────────────────────────
    def compute_rare_premium(self, ctx: RuleContext) -> float:
        total = 0.0
        for rule in self.rules["rare_premiums"]:
            if not eval_condition(rule["when"], ctx):
                continue
            formula = rule.get("formula")
            if formula:
                count = _num(ctx.get(formula["count_feature"]))
                if count is None:
                    count = float(formula.get("default_count", 1))
                extras = max(0.0, count - 1.0)
                total += formula["base"] + extras * formula["per_extra_unit"]
            else:
                total += rule["amount"]
        return total

    def compute_stat_premium(self, ctx: RuleContext) -> float:
        total = 0.0
        for rule in self.rules["stat_premiums"]:
            ladder = rule.get("ladder", [])
            first_match_only = rule.get("ladder_first_match", False)
            matched = False
            for step in ladder:
                if first_match_only and matched:
                    break
                if eval_condition(step["when"], ctx):
                    total += step["amount"]
                    matched = True
                    if not first_match_only:
                        continue  # independent tiers accumulate (legacy M4 tier)
        return total

    # ── caps ────────────────────────────────────────────────────────
    def apply_cap(
        self, ctx: RuleContext, fair_value: float, extra_premium: float, final_price: float
    ) -> dict[str, Any]:
        group = "with_m4" if ctx.get("_has_m4") else "no_m4"
        cap_rules = self.rules["caps"][group]

        view = {"_extra_premium": extra_premium}
        for rule in cap_rules:
            if not eval_condition(rule["when"], ctx, view):
                continue
            base = rule["base"]
            cap = base + extra_premium if rule["cap_mode"] == "base_plus_extra" else base
            new_value = min(fair_value, cap)
            return {
                "fair_value": new_value,
                "segment": rule["segment"],
                "confidence_margin": rule["confidence_margin"],
                "capped": True,
            }

        return {
            "fair_value": fair_value,
            "segment": None,
            "confidence_margin": None,
            "capped": False,
        }

    # ── multiple M4s ────────────────────────────────────────────────
    def apply_multi_m4(self, ctx: RuleContext, fair_value: float, segment: str) -> dict[str, Any]:
        cfg = self.rules["multi_m4"]
        account_data = ctx.account_data if isinstance(ctx.account_data, dict) else {}
        m4_count = account_data.get("m4_count", 1)

        result: dict[str, Any] = {"fair_value": fair_value, "segment": segment}
        if not isinstance(m4_count, (int, float)) or m4_count <= 1:
            return result

        result["segment"] = cfg["segment_label"]
        for i in range(2, int(m4_count) + 1):
            suffix = f"_{i}" if i > 1 else ""
            view = {
                "_extra_m4_is_max": account_data.get(f"m4{suffix}_is_max", False),
                "_extra_m4_level": account_data.get(f"m4{suffix}_level") or 1,
            }
            for step in cfg["per_extra_m4_ladder"]:
                if eval_condition(step["when"], ctx, view):
                    result["fair_value"] += step["amount"]
                    if i == 2:
                        result["segment"] += f" ({step['tag']})"
                    break

        if int(m4_count) > 2:
            for old, new in cfg["triple_word_replace"].items():
                result["segment"] = result["segment"].replace(old, new)
        return result

    # ── confidence ──────────────────────────────────────────────────
    def compute_confidence(self, ctx: RuleContext, final_price: float) -> dict[str, Any]:
        cfg = self.rules["confidence"]
        score = cfg["base_score"]

        values = {"final_price": final_price}
        for pen in cfg["price_penalties"]:
            if eval_condition(pen["when"], ctx, values):
                score -= pen["penalty"]

        rare_items = 0
        for feat in cfg["rare_item_features"]:
            raw = ctx.features.get(feat)
            rare_items += int(raw or 0)
        cars = _num(ctx.features.get("cars_mythic")) or 0
        rare_items += min(cfg["car_penalty_cap"], int(cars))
        score -= rare_items * cfg["rare_item_penalty_per_item"]

        lo, hi = cfg["clamp"]
        score = max(lo, min(hi, score))

        label = ""
        for lab in cfg["labels"]:
            if score >= lab["min_score"]:
                label = lab["label"]
                break

        return {"score": f"{score}%", "label": label}

    # ── blending ────────────────────────────────────────────────────
    def select_blend(self, lgb_price: float) -> dict[str, Any]:
        RuleContext(features={}, text="", _derived={})
        view = {"lgb_price": lgb_price}
        for key in ("cheap", "expensive"):
            blend = self.rules["blend"][key]
            when = blend["when"]
            if _cmp(view[when["feature"]["name"]], when["feature"]["op"], when["feature"]["value"]):
                weights = blend["weights"]
                return {
                    "weights": {
                        "xgboost": weights.get("xgboost", 0.0),
                        "lightgbm": weights.get("lightgbm", 0.0),
                        "catboost": weights.get("catboost", 0.0),
                    },
                    "segment": blend["segment"],
                    "confidence_margin": blend["confidence_margin"],
                }
        raise RuntimeError("No blend rule matched — pricing_rules.yaml misconfigured")

    # ── flipping margins ────────────────────────────────────────────
    def compute_flipping_advice(self, fair_value: float, asking_price: float) -> dict[str, Any]:
        cfg = self.rules["flipping"]
        buy_discount, sell_premium = cfg["tiers"][-1]["buy_discount"], cfg["tiers"][-1]["sell_premium"]
        for tier in cfg["tiers"]:
            cap = tier["max_fair_value"]
            if cap is None or fair_value < cap:
                buy_discount, sell_premium = tier["buy_discount"], tier["sell_premium"]
                break

        target_buy = int(fair_value * (1 - buy_discount))
        target_sell = int(fair_value * (1 + sell_premium))

        profit_at_asking = target_sell - asking_price
        profit_if_negotiated = target_sell - target_buy

        ratings = cfg["ratings"]
        if asking_price <= target_buy:
            rating = ratings["instant_buy"]
        elif asking_price <= fair_value:
            rating = ratings["fair"]
        else:
            rating = ratings["overpriced"]

        return {
            "deal_rating": rating,
            "asking_price": asking_price,
            "target_buy_price": target_buy,
            "target_sell_price": target_sell,
            "profit_if_bought_at_asking": profit_at_asking,
            "profit_if_negotiated": profit_if_negotiated,
            "negotiation_gain": profit_if_negotiated - profit_at_asking,
        }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    engine = PricingRulesEngine()
    print(f"Loaded pricing rules v{engine.version} "
          f"({len(engine.rules['rare_premiums'])} premium rules, "
          f"{len(engine.rules['caps']['no_m4']) + len(engine.rules['caps']['with_m4'])} cap rules)")
