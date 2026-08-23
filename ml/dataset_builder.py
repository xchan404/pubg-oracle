"""
Training Dataset Builder (Phase 3 flywheel)
Merges two label sources into one training frame:
  - 'asking'  : the historical CSV dataset (asking prices, abundant)
  - 'verified': human-labeled actual sale prices from the feedback store
                (scarce but ground truth — upweighted at train time)
Output: data/parsed/csv/training_dataset.csv (train.py auto-detects it).
"""

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Module-level so tests can monkeypatch it
from database.feedback import get_verified_sales  # noqa: E402

BASE_CSV = Path("data/parsed/csv/all_parsed_accounts.csv")
OUTPUT_CSV = Path("data/parsed/csv/training_dataset.csv")
VERIFIED_WEIGHT = 3.0
ASKING_WEIGHT = 1.0


def build_training_dataset(base_csv: Path = BASE_CSV,
                           output_csv: Path = OUTPUT_CSV) -> dict:
    """
    Returns a report dict; writes OUTPUT_CSV with a 'label_source' column.
    Verified rows get their price_egp replaced by the ACTUAL sale price —
    the model learns what accounts truly sold for, not what sellers asked.
    """
    # Idempotent: creates ads/deal_feedback tables if this DB predates them
    from database.ads import initialize as _ensure_schema
    from ml.pipeline import pipeline_instance
    _ensure_schema()

    if not base_csv.exists():
        raise FileNotFoundError(f"Base dataset missing: {base_csv}")

    df_base = pd.read_csv(base_csv, low_memory=False)
    if "label_source" not in df_base.columns:
        df_base["label_source"] = "asking"
    df_base["sample_weight"] = ASKING_WEIGHT
    n_asking = len(df_base)

    verified_rows = []
    skipped = 0
    for sale in get_verified_sales():
        try:
            features = pipeline_instance.process(sale["raw_text"] or "")
            row = {col: features.get(col) for col in df_base.columns
                   if col not in ("label_source", "sample_weight", "price_egp")}
            # Ground truth: what it actually sold for
            row["price_egp"] = float(sale["actual_price"])
            row["label_source"] = "verified"
            verified_rows.append(row)
        except Exception:
            skipped += 1

    df_verified = pd.DataFrame(verified_rows, columns=df_base.columns)
    if not df_verified.empty:
        df_verified["sample_weight"] = VERIFIED_WEIGHT
        combined = pd.concat([df_base, df_verified], ignore_index=True)
    else:
        combined = df_base
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_csv, index=False, encoding="utf-8-sig")

    return {
        "asking_rows": int(n_asking),
        "verified_rows": len(verified_rows),
        "verified_skipped_parse_failures": skipped,
        "total_rows": int(len(combined)),
        "output": str(output_csv),
        "verified_weight": VERIFIED_WEIGHT,
    }


if __name__ == "__main__":
    import json

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(build_training_dataset(), ensure_ascii=False, indent=2))
