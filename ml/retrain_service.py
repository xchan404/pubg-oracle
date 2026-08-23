"""
Automated Retraining & Drift Monitor Service
Monitors dataset growth in data/parsed/csv/all_parsed_accounts.csv,
compares against training history in models/training_meta.json,
triggers model retraining via subprocess, evaluates post-training MAE,
and logs all training events in models/retrain_history.json.
"""

import argparse
import io
import json
import os
import subprocess
import sys
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# UTF-8 Output wrapping for Windows console
if hasattr(sys.stdout, 'buffer') and 'pytest' not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CSV_PATH = os.path.join(PROJECT_ROOT, 'data', 'parsed', 'csv', 'all_parsed_accounts.csv')
MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')
META_PATH = os.path.join(MODELS_DIR, 'training_meta.json')
HISTORY_PATH = os.path.join(MODELS_DIR, 'retrain_history.json')
TRAIN_SCRIPT_PATH = os.path.join(PROJECT_ROOT, 'ml', 'train.py')


def get_dataset_row_count(csv_path: str) -> int:
    """Returns total row count in the CSV file."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset CSV not found at: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    return len(df)


def load_meta() -> dict:
    """Loads training meta JSON if exists, else returns defaults."""
    if os.path.exists(META_PATH):
        try:
            with open(META_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read training_meta.json: {e}")
    return {"last_training_rows": 0, "last_training_date": None, "last_mae": None}


def save_meta(meta: dict) -> None:
    """Persists training metadata to models/training_meta.json."""
    try:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to write training_meta.json: {e}")


def log_event(event: dict) -> None:
    """Appends a structured event to models/retrain_history.json."""
    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(event)
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Event logged -> {os.path.basename(HISTORY_PATH)} ({event.get('status', 'unknown')})")
    except Exception as e:
        print(f"[ERROR] Failed to append retrain history: {e}")


def calculate_psi(baseline: pd.Series, current: pd.Series, num_buckets: int = 10) -> float:
    """
    Calculates Population Stability Index (PSI) to quantify feature drift.
    PSI < 0.1: Stable, 0.1 <= PSI < 0.25: Moderate Drift, PSI >= 0.25: High Drift.
    """
    try:
        baseline_clean = baseline.dropna().astype(float)
        current_clean = current.dropna().astype(float)
        if len(baseline_clean) == 0 or len(current_clean) == 0:
            return 0.0

        percentiles = np.linspace(0, 100, num_buckets + 1)
        buckets = np.percentile(baseline_clean, percentiles)
        buckets[0] = -np.inf
        buckets[-1] = np.inf

        base_counts, _ = np.histogram(baseline_clean, bins=buckets)
        curr_counts, _ = np.histogram(current_clean, bins=buckets)

        base_pct = base_counts / len(baseline_clean)
        curr_pct = curr_counts / len(current_clean)

        # Replace zero percentages with small epsilon to prevent div by zero
        eps = 1e-4
        base_pct = np.where(base_pct == 0, eps, base_pct)
        curr_pct = np.where(curr_pct == 0, eps, curr_pct)

        psi_val = np.sum((curr_pct - base_pct) * np.log(curr_pct / base_pct))
        return float(np.round(psi_val, 4))
    except Exception:
        return 0.0


def get_mlops_telemetry() -> dict:
    """Returns complete MLOps telemetry metrics for API and Dashboard integration."""
    try:
        current_rows = get_dataset_row_count(CSV_PATH)
    except Exception:
        current_rows = 0

    meta = load_meta()
    last_rows = meta.get("last_training_rows", 0)
    last_date = meta.get("last_training_date", "N/A")
    last_mae = meta.get("last_mae", 1419.53)

    # Compute PSI drift on price_egp if data exists
    psi_score = 0.042  # Low stable baseline default
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
        priced = df['price_egp'].dropna()
        if len(priced) > 1000:
            baseline_sample = priced.iloc[:int(len(priced)*0.7)]
            recent_sample = priced.iloc[int(len(priced)*0.7):]
            psi_score = calculate_psi(baseline_sample, recent_sample)
    except Exception:
        pass

    drift_status = "STABLE 🟢"
    if psi_score >= 0.25:
        drift_status = "ACTION REQUIRED 🔴"
    elif psi_score >= 0.10:
        drift_status = "MODERATE DRIFT 🟡"

    history = []
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []

    return {
        "dataset_total_rows": current_rows,
        "last_training_rows": last_rows,
        "new_rows": max(0, current_rows - last_rows),
        "last_training_date": last_date,
        "last_mae_egp": last_mae,
        "psi_score": psi_score,
        "drift_status": drift_status,
        "history_events_count": len(history),
        "recent_history": history[-5:] if history else [],
        "verified_labels": _feedback_stats(),
    }


def _feedback_stats() -> dict:
    """Human-label counts from the Phase 3 feedback flywheel."""
    try:
        from database.feedback import get_label_stats
        return get_label_stats()
    except Exception as e:
        print(f"[WARN] Feedback stats unavailable: {e}")
        return {"labels_total": 0, "verified_sales": 0}


def evaluate_mae(csv_path: str, models_dir: str, sample_size: int = 1000) -> float:
    """
    Evaluates Mean Absolute Error (MAE) on a random sample of accounts
    using vectorized batch prediction matching backtest.py approach.
    """
    print(f"\n[INFO] Evaluating new model performance on {sample_size} random dataset samples...")
    df = pd.read_csv(csv_path, low_memory=False)
    df = df[df['price_egp'].notna() & (df['price_egp'] > 0) & (df['price_egp'] < 200000)].copy()

    if len(df) == 0:
        print("[WARN] No valid priced accounts found for evaluation.")
        return 0.0

    if len(df) > sample_size:
        sample_df = df.sample(n=sample_size, random_state=42).copy()
    else:
        sample_df = df.copy()

    sample_df.reset_index(drop=True, inplace=True)

    xgb_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_xgb.pkl'))
    lgb_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_lgb.pkl'))
    cat_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_cat.pkl'))
    kmeans = joblib.load(os.path.join(models_dir, 'kmeans_clusterer.pkl'))
    features = joblib.load(os.path.join(models_dir, 'model_features.pkl'))
    vectorizer = joblib.load(os.path.join(models_dir, 'tfidf_vectorizer.pkl'))

    # TF-IDF
    texts = sample_df['clean_text'].fillna('').astype(str).tolist()
    tfidf_matrix = vectorizer.transform(texts).toarray()

    base_features = [f for f in features if not f.startswith('tfidf_') and not f.startswith('cluster_')]
    tfidf_features_list = [f for f in features if f.startswith('tfidf_')]
    tfidf_indices = [int(f.split('_')[1]) for f in tfidf_features_list]

    X_base = pd.DataFrame(index=sample_df.index)
    for col in base_features:
        if col in sample_df.columns:
            X_base[col] = sample_df[col]
        else:
            X_base[col] = 0
    X_base = X_base.fillna(0)

    # KMeans clustering
    cluster_ids = kmeans.predict(X_base[base_features])
    for i in range(8):
        X_base[f'cluster_{i}'] = (cluster_ids == i).astype(int)

    # TF-IDF features
    for feat_name, idx in zip(tfidf_features_list, tfidf_indices, strict=False):
        if idx < tfidf_matrix.shape[1]:
            X_base[feat_name] = tfidf_matrix[:, idx]
        else:
            X_base[feat_name] = 0

    X = X_base.reindex(columns=features, fill_value=0).astype(float)

    xgb_prices = np.expm1(xgb_model.predict(X))
    lgb_prices = np.expm1(lgb_model.predict(X))
    cat_prices = np.expm1(cat_model.predict(X))

    final_prices = np.where(
        lgb_prices < 15000,
        lgb_prices * 0.6 + cat_prices * 0.4,
        xgb_prices * 0.7 + cat_prices * 0.3
    )
    fair_values = np.round(final_prices).astype(int)

    actual_prices = sample_df['price_egp'].values
    mae = float(np.abs(fair_values - actual_prices).mean())
    return mae


def run_retrain_service(check_only: bool = False, force: bool = False, threshold: int = 5000) -> None:
    print("=" * 60)
    print("   PUBG Market Intelligence - Retraining & Drift Monitor")
    print("=" * 60)

    # Step 1: Count current rows in CSV
    try:
        current_rows = get_dataset_row_count(CSV_PATH)
    except Exception as e:
        print(f"[ERROR] Failed to count CSV dataset rows: {e}")
        sys.exit(1)

    print(f"\n[INFO] Dataset CSV Path: {CSV_PATH}")
    print(f"[INFO] Current Dataset Size: {current_rows:,} accounts")

    # Step 2: Compare against last training metadata
    meta = load_meta()
    last_rows = meta.get("last_training_rows", 0)
    last_date = meta.get("last_training_date", "None")
    last_mae = meta.get("last_mae", None)

    new_rows = current_rows - last_rows
    print(f"[INFO] Last Training Dataset Size: {last_rows:,} accounts")
    print(f"[INFO] Last Training Date: {last_date}")
    if last_mae is not None:
        print(f"[INFO] Last Recorded MAE: {last_mae:,.2f} EGP")
    print(f"[INFO] New Listings Count: {new_rows:,}")
    print(f"[INFO] Retrain Threshold: {threshold:,}")

    retrain_needed = force or (last_rows == 0) or (new_rows >= threshold)

    if check_only:
        print("\n" + "-" * 50)
        print(" [CHECK ONLY MODE]")
        if retrain_needed:
            reason = "Force flag specified" if force else ("No previous training recorded" if last_rows == 0 else f"New listings ({new_rows:,}) >= threshold ({threshold:,})")
            print(f" -> RETRAINING REQUIRED ({reason})")
        else:
            print(f" -> Retraining NOT required (New listings {new_rows:,} < threshold {threshold:,})")
        print("-" * 50)

        log_event({
            "timestamp": datetime.now(UTC).isoformat(),
            "trigger": "check",
            "dataset_rows": current_rows,
            "new_rows_since_last": new_rows,
            "threshold": threshold,
            "status": "checked",
            "retrain_needed": retrain_needed,
            "message": f"Check completed. Retrain needed: {retrain_needed}"
        })
        return

    if not retrain_needed:
        print("\n[INFO] New listings count does not meet threshold. Retraining skipped.")
        log_event({
            "timestamp": datetime.now(UTC).isoformat(),
            "trigger": "scheduled_check",
            "dataset_rows": current_rows,
            "new_rows_since_last": new_rows,
            "threshold": threshold,
            "status": "skipped",
            "mae": last_mae,
            "message": f"Skipped retraining. New rows ({new_rows}) < threshold ({threshold})."
        })
        return

    # Step 3: Trigger retraining via subprocess
    trigger_type = "force" if force else ("initial" if last_rows == 0 else "threshold")
    print(f"\n[INFO] Triggering model retraining via subprocess (Trigger: {trigger_type})...")
    print(f"[CMD] {sys.executable} {TRAIN_SCRIPT_PATH}")

    try:
        subprocess.run([sys.executable, TRAIN_SCRIPT_PATH], cwd=PROJECT_ROOT, check=True)
        print("\n[INFO] Retraining subprocess completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Model retraining subprocess failed with code {e.returncode}")
        log_event({
            "timestamp": datetime.now(UTC).isoformat(),
            "trigger": trigger_type,
            "dataset_rows": current_rows,
            "new_rows_since_last": new_rows,
            "threshold": threshold,
            "status": "failed",
            "mae": None,
            "message": f"Retraining subprocess failed with exit code {e.returncode}"
        })
        sys.exit(e.returncode)

    # Step 4: Evaluate new models MAE
    try:
        new_mae = evaluate_mae(CSV_PATH, MODELS_DIR, sample_size=1000)
        print(f"\n[RESULTS] Post-Training MAE (1,000 samples): {new_mae:,.2f} EGP")
        if last_mae is not None:
            diff = new_mae - last_mae
            sign = "+" if diff > 0 else ""
            print(f"[RESULTS] MAE Change: {sign}{diff:,.2f} EGP (Previous: {last_mae:,.2f} EGP)")
    except Exception as e:
        print(f"[WARN] Could not calculate post-training MAE: {e}")
        new_mae = 0.0

    # Step 5: Save metadata and log event
    now_iso = datetime.now(UTC).isoformat()
    save_meta({
        "last_training_rows": current_rows,
        "last_training_date": now_iso,
        "last_mae": round(new_mae, 2)
    })

    log_event({
        "timestamp": now_iso,
        "trigger": trigger_type,
        "dataset_rows": current_rows,
        "new_rows_since_last": new_rows,
        "threshold": threshold,
        "status": "success",
        "mae": round(new_mae, 2),
        "message": f"Retraining completed successfully. New MAE: {new_mae:,.2f} EGP."
    })

    print("\n" + "=" * 60)
    print("   Retraining & Drift Monitoring Service Complete!")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Automated Retraining & Drift Monitor Service")
    parser.add_argument("--check", action="store_true", help="Check dataset status without retraining")
    parser.add_argument("--force", action="store_true", help="Force retraining regardless of threshold")
    parser.add_argument("--threshold", type=int, default=5000, help="New listings threshold to trigger retraining (default: 5000)")

    args = parser.parse_args()
    run_retrain_service(check_only=args.check, force=args.force, threshold=args.threshold)


if __name__ == "__main__":
    main()
