"""
Leakage Quantification A/B
Trains identical quick LightGBM models on the same data with two split
strategies and reports honest vs inflated test MAE:
  A) RANDOM row split  (legacy v1 behavior — reposts straddle both sides)
  B) GROUP split by account fingerprint (v2 — leak-free)
The gap between them is the amount the legacy evaluation was lying.
"""

import io
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import lightgbm as lgb
import numpy as np
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from ml.train import add_fingerprints, build_feature_frame, load_dataset

QUICK_PARAMS = dict(
    n_estimators=600, learning_rate=0.04, max_depth=7, num_leaves=48,
    subsample=0.85, colsample_bytree=0.85, objective="mae",
    random_state=42, n_jobs=-1, verbose=-1,
)


def evaluate(df, train_idx, test_idx, X_base):
    Xtr, Xte = X_base.iloc[train_idx], X_base.iloc[test_idx]
    ytr = np.log1p(df["price_egp"].iloc[train_idx])
    yte = np.log1p(df["price_egp"].iloc[test_idx])

    model = lgb.LGBMRegressor(**QUICK_PARAMS).fit(Xtr, ytr)
    preds_egp = np.expm1(model.predict(Xte))
    return float(mean_absolute_error(np.expm1(yte), preds_egp)), len(test_idx)


def main():
    df = add_fingerprints(load_dataset())
    df, X_base, _ = build_feature_frame(df)

    dup_rows = int(df.duplicated(subset=["account_fingerprint"]).sum())
    print(f"[INFO] Reposted rows (same fingerprint appears >1x): {dup_rows:,} "
          f"of {len(df):,} ({dup_rows / len(df) * 100:.1f}%)\n")

    # A) Legacy: random row split
    tr_a, te_a = train_test_split(np.arange(len(df)), test_size=0.15, random_state=42)
    mae_random, n_te = evaluate(df, tr_a, te_a, X_base)

    # B) v2: group split by fingerprint
    gss = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
    tr_b, te_b = next(gss.split(df, groups=df["account_fingerprint"]))
    mae_group, _ = evaluate(df, tr_b, te_b, X_base)

    inflation = (mae_random - mae_group) / mae_group * 100

    print("\n" + "=" * 56)
    print("   LEAKAGE QUANTIFICATION REPORT")
    print("=" * 56)
    print(f"   A) Random split MAE   : {mae_random:>10,.0f} EGP  (inflated/optimistic)")
    print(f"   B) Group split MAE    : {mae_group:>10,.0f} EGP  (honest estimate)")
    print(f"   Leakage inflation     : {inflation:+.1f}%")
    print("-" * 56)
    if inflation > 5:
        print("   VERDICT: legacy metrics were significantly overpromising.")
        print("   The group split is the number to trust going forward.")
    else:
        print("   VERDICT: leakage impact is modest; group split still safer.")
    print("=" * 56)


if __name__ == "__main__":
    main()
