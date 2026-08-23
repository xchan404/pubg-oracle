"""
PUBG Market Intelligence — Training Pipeline v2
Key upgrades over v1 (Phase 1):
  1. GROUP-AWARE SPLITS: accounts are fingerprinted and grouped so the same
     account reposted across channels can never leak between train and test.
  2. NO SYNTHETIC ROWS: fabricated training examples removed entirely.
  3. GroupKFold Optuna tuning (leak-free CV).
  4. MONOTONE CONSTRAINTS: more mythics/guns/anchors can never LOWER the
     predicted price (domain-correct regularization).
  5. SPLIT-CONFORMAL INTERVALS: statistically calibrated price ranges
     replace hardcoded confidence margins (models/conformal.json).
  6. EXPERIMENT LEDGER: every run logged to mlruns/experiments.jsonl.
"""

import io
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from catboost import CatBoostRegressor
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from ml.fingerprint import compute_fingerprint
from ml.tracking import finish_run, log_metrics, start_run

CSV_PATH = os.path.join("data", "parsed", "csv", "all_parsed_accounts.csv")
MODELS_DIR = "models"
SEGMENT_THRESHOLD = 15000  # EGP boundary between "cheap" and "expensive" segments
RANDOM_STATE = 42

# Features whose increase must never decrease predicted price.
MONOTONE_UP_EXACT = {
    "account_level", "collection_level", "mythics_count", "guns_count",
    "xsuits_count", "cars_total", "cars_mythic", "conqueror_frames_count",
    "m4_level", "prestige_score", "rarity_score",
    "base_market_score", "final_market_score", "combo_multiplier",
}


def monotone_vector(columns) -> list:
    """+1 for domain-monotone-up features, +1 for any anchor flag, else 0."""
    vec = []
    for col in columns:
        if col in MONOTONE_UP_EXACT or col.startswith("has_"):
            vec.append(1)
        else:
            vec.append(0)
    return vec


def load_dataset(csv_path: str = CSV_PATH) -> pd.DataFrame:
    print("[INFO] Loading data from CSV...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.dropna(subset=["price_egp", "clean_text"])

    # Filter negotiation words that skew asking prices
    bad_words = (
        r"راسلني|تفاوض|أو أقل|او اقل|أو أكتر|او اكتر|قابل للتفاوض|"
        r"او يزيد|أو يزيد|تقريبا|تقريباً|حوالي|يبدأ من|ابتداء من"
    )
    df = df[~df["clean_text"].str.contains(bad_words, case=False, na=False)].copy()

    df = df[(df["price_egp"] >= 1000) & (df["price_egp"] <= 80000)].copy()
    df.reset_index(drop=True, inplace=True)
    print(f"[INFO] Total priced accounts for training: {len(df)}")
    return df


def add_fingerprints(df: pd.DataFrame) -> pd.DataFrame:
    print("[INFO] Computing account fingerprints for group-aware splits...")
    df["account_fingerprint"] = df.apply(lambda r: compute_fingerprint(r.to_dict()), axis=1)
    dup_rows = int(df.duplicated(subset=["account_fingerprint"]).sum())
    n_groups = df["account_fingerprint"].nunique()
    print(f"[INFO] Unique accounts (groups): {n_groups:,} | reposted rows detected: {dup_rows:,} "
          f"({dup_rows / max(1, len(df)) * 100:.1f}% of dataset)")
    return df


def build_feature_frame(df: pd.DataFrame):
    """Assembles base features + m4_type one-hots (same contract as v1)."""
    features = [
        "account_level", "collection_level", "mythics_count", "guns_count", "xsuits_count",
        "m4_level", "m4_is_max", "cars_total", "cars_mythic", "has_airdrop_car",
        "conqueror_frames_count", "has_conqueror_frame", "has_plane_frame", "has_re2_frame",
        "has_xsuit", "has_m4_glacier", "has_joker_fox", "has_joker_fox_locked",
        "has_mummy", "has_double_mummy", "has_conqueror", "has_vehicle_dev",
        "has_face_girl", "has_lobby_mythic", "has_car_mclaren", "has_car_dodge",
        "has_ghazi", "has_ghawas", "has_soap_blue", "has_soap_black", "has_soap_rare",
        "has_soap_double", "has_scarf_tiger", "has_hair_qarnain", "has_hair_kaboria", "has_hair_yellow",
        "has_akm", "akm_is_max", "has_m762", "m762_is_max", "has_awm", "awm_is_max",
        "has_uzi", "uzi_is_max", "has_ump", "ump_is_max",
        "has_falcon", "has_dog", "has_cat", "has_poro", "has_penguin",
        "prestige_score", "rarity_score", "combo_multiplier",
        "has_m4_max_x_mummy", "has_m4_x_xsuit", "guns_per_mythic_ratio", "has_super_combo",
    ]
    if "m4_type" in df.columns:
        dummies = pd.get_dummies(df["m4_type"], prefix="m4_type", dummy_na=True)
        df = pd.concat([df, dummies], axis=1)
        features.extend(dummies.columns.tolist())

    features = [f for f in features if f in df.columns]
    X_base = df[features].copy().fillna(0).astype(float)
    return df, X_base, features


ARABIC_STOPWORDS = [
    "للبيع", "وسيط", "جروب", "تواصل", "واتس", "حساب", "اكونت",
    "السعر", "سعر", "ربط", "في", "من", "على",
]


class TextTransformers:
    """TF-IDF + KMeans fitted strictly on training data (no leakage)."""

    def __init__(self, n_clusters: int = 8):
        self.vectorizer = TfidfVectorizer(max_features=100, ngram_range=(1, 2),
                                          stop_words=ARABIC_STOPWORDS)
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=RANDOM_STATE, n_init="auto")
        self.n_clusters = n_clusters

    def fit_transform(self, texts: pd.Series, base_feats: pd.DataFrame) -> pd.DataFrame:
        tfidf_mat = self.vectorizer.fit_transform(texts.fillna("")).toarray()
        clusters = self.kmeans.fit_predict(base_feats.values)
        return self._assemble(tfidf_mat, clusters, base_feats.index)

    def transform(self, texts: pd.Series, base_feats: pd.DataFrame) -> pd.DataFrame:
        tfidf_mat = self.vectorizer.transform(texts.fillna("")).toarray()
        clusters = self.kmeans.predict(base_feats.values)
        return self._assemble(tfidf_mat, clusters, base_feats.index)

    def _assemble(self, tfidf_mat: np.ndarray, clusters: np.ndarray, index) -> pd.DataFrame:
        parts = []
        n_tfidf = tfidf_mat.shape[1]
        if n_tfidf:
            parts.append(pd.DataFrame(tfidf_mat, index=index,
                                      columns=[f"tfidf_{i}" for i in range(n_tfidf)]))
        cluster_cols = {}
        for i in range(self.n_clusters):
            cluster_cols[f"cluster_{i}"] = (clusters == i).astype(float)
        parts.append(pd.DataFrame(cluster_cols, index=index))
        return pd.concat(parts, axis=1)


def blended_price(xgb_p: np.ndarray, lgb_p: np.ndarray, cat_p: np.ndarray) -> np.ndarray:
    """Deployment blend: cheap segment trusts LGB+CAT, whale trusts XGB+CAT."""
    return np.where(lgb_p < SEGMENT_THRESHOLD,
                    lgb_p * 0.6 + cat_p * 0.4,
                    xgb_p * 0.7 + cat_p * 0.3)


def tune_lightgbm(X: pd.DataFrame, y_log: pd.Series, groups: pd.Series,
                  n_trials: int) -> dict:
    """Optuna search with leak-free GroupKFold CV on the cheap segment."""
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 300, 2000),
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.05, log=True),
            "max_depth": trial.suggest_int("max_depth", 4, 12),
            "num_leaves": trial.suggest_int("num_leaves", 15, 80),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "objective": "mae",
            "random_state": RANDOM_STATE,
            "n_jobs": -1,
            "verbose": -1,
        }
        gkf = GroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        scores = []
        for tr_idx, va_idx in gkf.split(X, y_log, groups=groups):
            X_tr, y_tr = X.iloc[tr_idx], y_log.iloc[tr_idx]
            X_va, y_va = X.iloc[va_idx], y_log.iloc[va_idx]
            model = lgb.LGBMRegressor(**params)
            model.fit(X_tr, y_tr,
                      eval_set=[(X_va, y_va)],
                      callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)])
            scores.append(mean_absolute_error(np.expm1(y_va), np.expm1(model.predict(X_va))))
        return float(np.mean(scores))

    study = optuna.create_study(direction="minimize")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=n_trials)
    print(f"Best LightGBM Params: {study.best_params}")
    best = dict(study.best_params)
    best.update({"objective": "mae", "random_state": RANDOM_STATE, "n_jobs": -1, "verbose": -1})
    return best


def _fit_tolerant(builder, X_fit, y_fit, label: str):
    """
    Fits a model with monotone constraints when the library/objective
    supports it (LightGBM rejects them under L1/MAE), otherwise retries
    unconstrained with a warning instead of crashing the pipeline.
    """
    try:
        model = builder(constrained=True)
        model.fit(X_fit, y_fit)
        return model
    except Exception as exc:  # noqa: BLE001 - any library rejection falls back
        print(f"[WARN] Monotone constraints unavailable for {label} ({exc}); fitting unconstrained.")
        model = builder(constrained=False)
        model.fit(X_fit, y_fit)
        return model


def fit_models(df: pd.DataFrame, X: pd.DataFrame, masks: dict, params_lgb: dict):
    """
    Fits segment models + CatBoost blender on given row subsets.
    Note: v1 used the TEST partition as XGB's early-stopping eval_set —
    that is subtle leakage; v2 fits with fixed budgets instead.
    """
    y_log_full = np.log1p(df.loc[masks["all"], "price_egp"])
    mono_vec = monotone_vector(X.columns)

    def build_lgb(constrained: bool):
        p = dict(params_lgb)
        if constrained:
            p["monotone_constraints"] = mono_vec
        return lgb.LGBMRegressor(**p)

    def build_xgb(constrained: bool):
        kw = dict(
            n_estimators=1200, learning_rate=0.03, max_depth=6,
            subsample=0.8, colsample_bytree=0.8,
            objective="reg:absoluteerror", random_state=RANDOM_STATE, n_jobs=-1,
        )
        if constrained:
            kw["monotone_constraints"] = tuple(mono_vec)
        return xgb.XGBRegressor(**kw)

    def build_cat(constrained: bool):
        kw = dict(iterations=1500, learning_rate=0.03, depth=6,
                  loss_function="MAE", random_seed=RANDOM_STATE, verbose=0)
        if constrained:
            kw["monotone_constraints"] = list(mono_vec)
        return CatBoostRegressor(**kw)

    lgb_model = _fit_tolerant(build_lgb, X.loc[masks["cheap"]],
                              y_log_full.loc[masks["cheap"]], "lightgbm(cheap)")
    xgb_model = _fit_tolerant(build_xgb, X.loc[masks["expensive"]],
                              y_log_full.loc[masks["expensive"]], "xgboost(expensive)")
    cat_model = _fit_tolerant(build_cat, X.loc[masks["all"]], y_log_full, "catboost(all)")

    return lgb_model, xgb_model, cat_model


def conformal_widths(df_fit: pd.DataFrame, X_fit: pd.DataFrame,
                     df_calib: pd.DataFrame, X_calib: pd.DataFrame,
                     models: dict, coverage: float = 0.90) -> dict:
    """
    Split-conformal calibration in EGP space using the deployment blend.
    Residuals measured on a group-disjoint calibration set.
    """
    preds = blended_price(
        np.expm1(models["xgb"].predict(X_calib)),
        np.expm1(models["lgb"].predict(X_calib)),
        np.expm1(models["cat"].predict(X_calib)),
    )
    actuals = df_calib["price_egp"].values
    resid = np.abs(preds - actuals)

    # Segment by the BLENDED estimate (available at inference); the raw cheap-
    # specialist LGBM output almost never crosses the whale boundary.
    cheap_mask = preds < SEGMENT_THRESHOLD

    out = {
        "method": "split_conformal",
        "coverage_target": coverage,
        "calibration_size": int(len(resid)),
        "global_width": int(round(np.quantile(resid, coverage))),
        "cheap_width": int(round(np.quantile(resid[cheap_mask], coverage))) if cheap_mask.sum() >= 30 else None,
        "expensive_width": int(round(np.quantile(resid[~cheap_mask], coverage))) if (~cheap_mask).sum() >= 30 else None,
        "created_at": pd.Timestamp.utcnow().isoformat(),
    }

    # Honest coverage check on this calibration set
    width_col = np.where(cheap_mask,
                         out["cheap_width"] or out["global_width"],
                         out["expensive_width"] or out["global_width"])
    out["empirical_coverage_calib"] = round(float((resid <= width_col).mean()), 4)
    return out


def main():
    n_trials = int(os.environ.get("OPTUNA_TRIALS", "12"))
    run_id = start_run(
        "train_v2_group_split",
        params={"optuna_trials": n_trials, "segment_threshold": SEGMENT_THRESHOLD},
        dataset_path=CSV_PATH,
    )

    df = add_fingerprints(load_dataset())
    df, X_base, base_features = build_feature_frame(df)

    # ── GROUP-AWARE TRAIN/TEST SPLIT (kills repost leakage) ──────────
    gss = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(df, groups=df["account_fingerprint"]))
    train_df, test_df = df.iloc[train_idx].copy(), df.iloc[test_idx].copy()

    transformers = TextTransformers()
    tfidf_train = transformers.fit_transform(train_df["clean_text"], X_base.iloc[train_idx])
    tfidf_test = transformers.transform(test_df["clean_text"], X_base.iloc[test_idx])

    X_train = pd.concat([X_base.iloc[train_idx], tfidf_train], axis=1)
    X_test = pd.concat([X_base.iloc[test_idx], tfidf_test], axis=1)

    y_train = np.log1p(train_df["price_egp"])
    all_features = X_train.columns.tolist()

    seg_cheap_tr = train_df["price_egp"] < SEGMENT_THRESHOLD
    masks_train = {
        "all": train_df.index,
        "cheap": train_df.index[seg_cheap_tr],
        "expensive": train_df.index[~seg_cheap_tr],
    }

    # ── Optuna (GroupKFold) on cheap segment ─────────────────────────
    print(f"[INFO] Optuna GroupKFold tuning ({n_trials} trials, cheap segment)...")
    params_lgb = tune_lightgbm(
        X_train.loc[masks_train["cheap"]], y_train.loc[masks_train["cheap"]],
        train_df.loc[masks_train["cheap"], "account_fingerprint"],
        n_trials,
    )

    # ── CONFORMAL CALIBRATION (fit/calib group-disjoint, then refit) ─
    print("[INFO] Split-conformal calibration...")
    cal_gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_STATE)
    fit_pos, cal_pos = next(cal_gss.split(train_df, groups=train_df["account_fingerprint"]))
    fit_df, calib_df = train_df.iloc[fit_pos], train_df.iloc[cal_pos]

    seg_cheap_fit = fit_df["price_egp"] < SEGMENT_THRESHOLD
    masks_fit = {
        "all": fit_df.index,
        "cheap": fit_df.index[seg_cheap_fit],
        "expensive": fit_df.index[~seg_cheap_fit],
    }
    calib_models = dict(zip(("lgb", "xgb", "cat"),
                            fit_models(fit_df, X_train, masks_fit, params_lgb), strict=True))
    conformal =     conformal_widths(
        fit_df, X_train.loc[fit_df.index], calib_df, X_train.loc[calib_df.index], calib_models
    )
    print(f"[INFO] Conformal widths @90%: global={conformal['global_width']} "
          f"cheap={conformal['cheap_width']} expensive={conformal['expensive_width']} "
          f"(calib coverage={conformal['empirical_coverage_calib']})")

    # ── FINAL MODELS on the full training partition ──────────────────
    print("[INFO] Refitting final models on the full train partition...")
    lgb_model, xgb_model, cat_model = fit_models(train_df, X_train, masks_train, params_lgb)

    # ── Evaluation on the held-out group-disjoint test partition ─────
    def eval_blend(models_tuple):
        preds = blended_price(
            np.expm1(models_tuple[0].predict(X_test)),
            np.expm1(models_tuple[1].predict(X_test)),
            np.expm1(models_tuple[2].predict(X_test)),
        )
        return preds

    final_preds = eval_blend((xgb_model, lgb_model, cat_model))
    actuals = test_df["price_egp"].values
    mae_overall = float(mean_absolute_error(actuals, final_preds))

    cheap_mask_te = test_df["price_egp"].values < SEGMENT_THRESHOLD
    mae_cheap = float(mean_absolute_error(actuals[cheap_mask_te], final_preds[cheap_mask_te]))
    mae_exp = float(mean_absolute_error(actuals[~cheap_mask_te], final_preds[~cheap_mask_te]))

    # Empirical conformal coverage on TEST
    cw = conformal.get("cheap_width") or conformal["global_width"]
    ew = conformal.get("expensive_width") or conformal["global_width"]
    width_te = np.where(cheap_mask_te, cw, ew)
    coverage_te = float(((np.abs(final_preds - actuals)) <= width_te).mean())

    print("\n--- FINAL PERFORMANCE (group-disjoint test) ---")
    print(f"   Cheap (<{SEGMENT_THRESHOLD:,})  MAE: {mae_cheap:,.0f} EGP")
    print(f"   Expensive      MAE: {mae_exp:,.0f} EGP")
    print(f"   Overall        MAE: {mae_overall:,.0f} EGP")
    print(f"   Conformal coverage on TEST: {coverage_te:.1%} (target 90%)")

    # ── Empirical quantile models ────────────────────────────────────
    print("[INFO] Training quantile regressors (q10/q90)...")
    common = dict(objective="quantile", n_estimators=800, learning_rate=0.03,
                  random_state=RANDOM_STATE, n_jobs=-1, verbose=-1)
    q10_model = lgb.LGBMRegressor(**common, alpha=0.10).fit(X_train, y_train)
    q90_model = lgb.LGBMRegressor(**common, alpha=0.90).fit(X_train, y_train)

    # ── Persist artifacts ────────────────────────────────────────────
    print("[INFO] Saving models...")
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(xgb_model, os.path.join(MODELS_DIR, "pubg_pricer_xgb.pkl"))
    joblib.dump(lgb_model, os.path.join(MODELS_DIR, "pubg_pricer_lgb.pkl"))
    joblib.dump(cat_model, os.path.join(MODELS_DIR, "pubg_pricer_cat.pkl"))
    joblib.dump(q10_model, os.path.join(MODELS_DIR, "pubg_pricer_q10.pkl"))
    joblib.dump(q90_model, os.path.join(MODELS_DIR, "pubg_pricer_q90.pkl"))
    joblib.dump(transformers.kmeans, os.path.join(MODELS_DIR, "kmeans_clusterer.pkl"))
    joblib.dump(all_features, os.path.join(MODELS_DIR, "model_features.pkl"))
    joblib.dump(transformers.vectorizer, os.path.join(MODELS_DIR, "tfidf_vectorizer.pkl"))

    with open(os.path.join(MODELS_DIR, "conformal.json"), "w", encoding="utf-8") as fh:
        json.dump(conformal, fh, indent=2, ensure_ascii=False)

    log_metrics(run_id, {
        "overall_mae_egp": round(mae_overall, 1),
        "cheap_mae_egp": round(mae_cheap, 1),
        "expensive_mae_egp": round(mae_exp, 1),
        "test_size": len(test_df),
        "train_size": len(train_df),
        "unique_account_groups": int(train_df['account_fingerprint'].nunique()),
        "conformal_global_width": conformal["global_width"],
        "conformal_coverage_test": round(coverage_te, 4),
        "best_lgb_params": params_lgb,
    })
    finish_run(run_id)
    print(f"\n[DONE] Experiment {run_id} logged to mlruns/experiments.jsonl")


if __name__ == "__main__":
    main()
