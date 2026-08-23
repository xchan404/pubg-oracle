"""
PUBG Market Intelligence — Ensemble Pricer
Thin orchestration layer: builds the feature vector, runs the three
gradient-boosting models + quantile bounds, then delegates ALL business
logic (premiums, caps, multi-M4, confidence, flipping margins) to the
declarative PricingRulesEngine (config/pricing_rules.yaml).
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore', category=FutureWarning)

from ml.pipeline import pipeline_instance
from ml.rules_engine import PricingRulesEngine, build_context


class EnsemblePricer:
    def __init__(self, models_dir='models'):
        self.xgb_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_xgb.pkl'))
        self.lgb_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_lgb.pkl'))
        self.cat_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_cat.pkl'))
        self.kmeans = joblib.load(os.path.join(models_dir, 'kmeans_clusterer.pkl'))
        self.features = joblib.load(os.path.join(models_dir, 'model_features.pkl'))
        self.vectorizer = joblib.load(os.path.join(models_dir, 'tfidf_vectorizer.pkl'))

        # Quantile models for empirical bounds
        q10_path = os.path.join(models_dir, 'pubg_pricer_q10.pkl')
        q90_path = os.path.join(models_dir, 'pubg_pricer_q90.pkl')
        self.q10_model = joblib.load(q10_path) if os.path.exists(q10_path) else None
        self.q90_model = joblib.load(q90_path) if os.path.exists(q90_path) else None

        # Declarative business rules (premiums / caps / confidence / flipping)
        self.rules_engine = PricingRulesEngine()

    # ──────────────────────────────────────────────────────────────
    def _build_vector(self, account_data) -> tuple:
        """Builds the ordered feature row expected by the models."""
        df = pd.DataFrame([account_data])

        for col in self.features:
            if col not in df.columns and not col.startswith('tfidf_') and not col.startswith('cluster_'):
                df[col] = 0

        text = str(df['clean_text'].iloc[0]) if 'clean_text' in df.columns else ''
        tfidf_features = self.vectorizer.transform([text]).toarray()

        X_dict = {}
        for col in self.features:
            if col.startswith('tfidf_'):
                idx = int(col.split('_')[1])
                X_dict[col] = tfidf_features[0][idx]
            elif not col.startswith('cluster_'):
                X_dict[col] = df[col].iloc[0] if col in df.columns else 0

        base_features = [f for f in self.features if not f.startswith('tfidf_') and not f.startswith('cluster_')]
        base_df = pd.DataFrame([X_dict])[base_features].astype(float).fillna(0.0)
        cluster_id = self.kmeans.predict(base_df)[0]

        for i in range(8):
            X_dict[f'cluster_{i}'] = 1 if i == cluster_id else 0

        X = pd.DataFrame([X_dict])[self.features].astype(float).fillna(0)
        return X, df, text

    # ──────────────────────────────────────────────────────────────
    def predict(self, account_data, asking_price: float | None = None) -> dict:
        """
        Takes a dictionary of account features OR a raw text string, and an optional asking price.
        Returns the predicted fair value and arbitrage negotiation details.
        """
        if isinstance(account_data, str):
            account_data = pipeline_instance.process(account_data)

        X, df, text = self._build_vector(account_data)

        xgb_price = np.expm1(self.xgb_model.predict(X)[0])
        lgb_price = np.expm1(self.lgb_model.predict(X)[0])
        cat_price = np.expm1(self.cat_model.predict(X)[0])

        q10_price = np.expm1(self.q10_model.predict(X)[0]) if self.q10_model else None
        q90_price = np.expm1(self.q90_model.predict(X)[0]) if self.q90_model else None

        # ── Blend per segment (weights from pricing_rules.yaml) ──
        blend = self.rules_engine.select_blend(float(lgb_price))
        w = blend["weights"]
        final_price = (
            xgb_price * w["xgboost"] + lgb_price * w["lightgbm"] + cat_price * w["catboost"]
        )
        segment = blend["segment"]
        confidence_margin = blend["confidence_margin"]

        fair_value = round(final_price)

        # ── Business rules via declarative engine ────────────────
        ctx = build_context(
            features=df.iloc[0].to_dict(),
            text=text,
            account_data=account_data if isinstance(account_data, dict) else {},
        )

        rare_premium = self.rules_engine.compute_rare_premium(ctx)
        fair_value += rare_premium

        stat_premium = self.rules_engine.compute_stat_premium(ctx)
        extra_premium = rare_premium + stat_premium

        cap_outcome = self.rules_engine.apply_cap(ctx, fair_value, extra_premium, final_price)
        fair_value = cap_outcome["fair_value"]
        if cap_outcome["capped"]:
            segment = cap_outcome["segment"]
            confidence_margin = cap_outcome["confidence_margin"]

        multi_outcome = self.rules_engine.apply_multi_m4(ctx, fair_value, segment)
        fair_value = multi_outcome["fair_value"]
        segment = multi_outcome["segment"]

        model_was_overridden = (not ctx.get("_has_m4")) and (round(final_price) != fair_value)

        # ── Confidence score ─────────────────────────────────────
        confidence = self.rules_engine.compute_confidence(ctx, final_price)

        # ── Empirical price bounds ───────────────────────────────
        if q10_price and q90_price:
            lower_bound = max(0, int(round(q10_price)))
            upper_bound = max(lower_bound + 100, int(round(q90_price)))
            price_range_str = f"{lower_bound} - {upper_bound} EGP"
        else:
            price_range_str = f"{max(0, fair_value - confidence_margin)} - {fair_value + confidence_margin} EGP"

        result = {
            "fair_value_egp": fair_value,
            "price_range": price_range_str,
            "segment": segment,
            "confidence": confidence,
            "models_breakdown": {
                "xgboost_estimate": int(xgb_price),
                "lightgbm_estimate": int(lgb_price),
                "catboost_estimate": int(cat_price),
                "note": (
                    "⚠️ القيمة النهائية اتعدلت بواسطة Business Rules (السقف السعري)"
                    if model_was_overridden
                    else "✅ القيمة النهائية مباشرة من الموديل"
                ),
            },
        }

        # ── Arbitrage / Flipping Engine ──────────────────────────
        if asking_price is not None:
            result["flipping_advice"] = self.rules_engine.compute_flipping_advice(
                float(fair_value), float(asking_price)
            )

        return result


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    pricer = EnsemblePricer()

    test_1: dict = {}
    test_2 = {'m4_level': 7, 'm4_is_max': 1, 'has_m4_glacier': 1, 'account_level': 70, 'guns_count': 1}
    test_3 = {
        'cars_total': 5, 'has_mummy': 1, 'has_car_mclaren': 1, 'm4_level': 7, 'm4_is_max': 1,
        'has_m4_glacier': 1, 'mythics_count': 50, 'account_level': 85,
        'has_akm': 1, 'akm_is_max': 1, 'has_falcon': 1,
    }

    print("--- ARBITRAGE PREDICTIONS TEST ---")
    print("\n1. Empty Account:")
    print(pricer.predict(test_1))

    print("\n2. M4 Max Account:")
    print(pricer.predict(test_2))

    print("\n3. Whale Account (Asking 9000 EGP):")
    import json
    print(json.dumps(pricer.predict(test_3, asking_price=9000), indent=2, ensure_ascii=False))
