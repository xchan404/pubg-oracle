"""
PUBG Market Intelligence - Automated Backtesting & Deal Profitability Engine
Evaluates model performance against historical accounts using FAST batch predictions.
Calculates real-world flipping ROI, profit margins, deal hit rate, and segment accuracy.
"""

import io
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import joblib
import numpy as np
import pandas as pd

# ─── Configuration ───────────────────────────────────────────
FLIP_SELL_MARGIN = 0.10       # 10% markup when reselling
NEGOTIATION_DISCOUNT = 0.20   # Assume we negotiate 20% off asking price
MIN_PROFIT_EGP = 300          # Minimum profit to consider a deal worthwhile
CSV_PATH = os.path.join('data', 'parsed', 'csv', 'all_parsed_accounts.csv')
MODELS_DIR = 'models'


def run_backtest(max_accounts: int = None):
    print("=" * 60)
    print("  PUBG Deal Profitability Backtest Engine (Vectorized)")
    print("=" * 60)

    # ─── Step 1: Load Data ───────────────────────────────────
    print("\n[1/4] Loading priced accounts from CSV...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    df = df[df['price_egp'].notna() & (df['price_egp'] > 0) & (df['price_egp'] < 200000)].copy()
    df.reset_index(drop=True, inplace=True)
    total = len(df)
    print(f"       Found {total:,} accounts with valid asking prices.")

    if max_accounts:
        df = df.head(max_accounts)
        print(f"       (Limited to first {max_accounts:,} for speed)")

    # ─── Step 2: Load Models ─────────────────────────────────
    print("\n[2/4] Loading model artifacts...")
    xgb_model = joblib.load(os.path.join(MODELS_DIR, 'pubg_pricer_xgb.pkl'))
    lgb_model = joblib.load(os.path.join(MODELS_DIR, 'pubg_pricer_lgb.pkl'))
    cat_model = joblib.load(os.path.join(MODELS_DIR, 'pubg_pricer_cat.pkl'))
    kmeans = joblib.load(os.path.join(MODELS_DIR, 'kmeans_clusterer.pkl'))
    features = joblib.load(os.path.join(MODELS_DIR, 'model_features.pkl'))
    vectorizer = joblib.load(os.path.join(MODELS_DIR, 'tfidf_vectorizer.pkl'))

    q10_path = os.path.join(MODELS_DIR, 'pubg_pricer_q10.pkl')
    q90_path = os.path.join(MODELS_DIR, 'pubg_pricer_q90.pkl')
    q10_model = joblib.load(q10_path) if os.path.exists(q10_path) else None
    q90_model = joblib.load(q90_path) if os.path.exists(q90_path) else None
    print("       All models loaded.")

    # ─── Step 3: Vectorized Batch Prediction ─────────────────
    print(f"\n[3/4] Running vectorized batch predictions on {len(df):,} accounts...")

    # TF-IDF
    texts = df['clean_text'].fillna('').astype(str).tolist()
    tfidf_matrix = vectorizer.transform(texts).toarray()

    # Build feature matrix
    base_features = [f for f in features if not f.startswith('tfidf_') and not f.startswith('cluster_')]
    tfidf_features_list = [f for f in features if f.startswith('tfidf_')]
    tfidf_indices = [int(f.split('_')[1]) for f in tfidf_features_list]

    X_base = pd.DataFrame(index=df.index)
    for col in base_features:
        if col in df.columns:
            X_base[col] = df[col]
        else:
            X_base[col] = 0
    X_base = X_base.fillna(0)

    # KMeans clustering
    cluster_ids = kmeans.predict(X_base[base_features])
    for i in range(8):
        X_base[f'cluster_{i}'] = (cluster_ids == i).astype(int)

    # Add TF-IDF columns
    for feat_name, idx in zip(tfidf_features_list, tfidf_indices, strict=False):
        if idx < tfidf_matrix.shape[1]:
            X_base[feat_name] = tfidf_matrix[:, idx]
        else:
            X_base[feat_name] = 0

    # Reorder to model feature order
    X = X_base.reindex(columns=features, fill_value=0).astype(float)

    # Predict all at once
    xgb_prices = np.expm1(xgb_model.predict(X))
    lgb_prices = np.expm1(lgb_model.predict(X))
    cat_prices = np.expm1(cat_model.predict(X))

    q10_prices = np.expm1(q10_model.predict(X)) if q10_model else np.zeros(len(X))
    q90_prices = np.expm1(q90_model.predict(X)) if q90_model else np.zeros(len(X))

    # Blend: Economy uses LGB+CAT, Whale uses XGB+CAT
    final_prices = np.where(
        lgb_prices < 15000,
        lgb_prices * 0.6 + cat_prices * 0.4,
        xgb_prices * 0.7 + cat_prices * 0.3
    )
    fair_values = np.round(final_prices).astype(int)
    print("       Batch prediction complete.")

    # ─── Step 4: Profitability Analysis ──────────────────────
    print("\n[4/4] Analyzing profitability metrics...")
    asking_prices = df['price_egp'].values

    negotiated_buy = asking_prices * (1 - NEGOTIATION_DISCOUNT)
    target_sell = fair_values * (1 + FLIP_SELL_MARGIN)
    profit_at_asking = target_sell - asking_prices
    profit_negotiated = target_sell - negotiated_buy
    pct_error = np.abs(fair_values - asking_prices) / asking_prices * 100

    is_underpriced = fair_values > asking_prices * 1.15
    is_overpriced = fair_values < asking_prices * 0.80

    res_df = pd.DataFrame({
        'asking_price': asking_prices,
        'fair_value': fair_values,
        'q10_bound': np.round(q10_prices).astype(int),
        'q90_bound': np.round(q90_prices).astype(int),
        'lgb_price': np.round(lgb_prices).astype(int),
        'xgb_price': np.round(xgb_prices).astype(int),
        'cat_price': np.round(cat_prices).astype(int),
        'negotiated_buy': np.round(negotiated_buy).astype(int),
        'target_sell': np.round(target_sell).astype(int),
        'profit_at_asking': np.round(profit_at_asking).astype(int),
        'profit_negotiated': np.round(profit_negotiated).astype(int),
        'is_underpriced': is_underpriced,
        'is_overpriced': is_overpriced,
        'pct_error': np.round(pct_error, 1),
    })

    total_accounts = len(res_df)
    mape = res_df['pct_error'].mean()
    mae_egp = np.abs(fair_values - asking_prices).mean()

    underpriced_df = res_df[res_df['is_underpriced']]
    overpriced_df = res_df[res_df['is_overpriced']]
    fair_priced_df = res_df[~res_df['is_underpriced'] & ~res_df['is_overpriced']]

    profitable_ask = res_df[res_df['profit_at_asking'] >= MIN_PROFIT_EGP]
    profitable_neg = res_df[res_df['profit_negotiated'] >= MIN_PROFIT_EGP]

    economy = res_df[res_df['asking_price'] < 15000]
    whale = res_df[res_df['asking_price'] >= 15000]

    # ─── Print Report ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS REPORT")
    print("=" * 60)

    print(f"\n  Total Accounts Evaluated      : {total_accounts:,}")
    print(f"  Mean Absolute Error (MAE)     : {mae_egp:,.0f} EGP")
    print(f"  Mean Absolute % Error (MAPE)  : {mape:.1f}%")

    print("\n--- Deal Classification ---")
    print(f"  Underpriced (Fair > Ask*1.15)  : {len(underpriced_df):,} ({len(underpriced_df)/total_accounts*100:.1f}%)")
    print(f"  Fair Priced                    : {len(fair_priced_df):,} ({len(fair_priced_df)/total_accounts*100:.1f}%)")
    print(f"  Overpriced  (Fair < Ask*0.80)  : {len(overpriced_df):,} ({len(overpriced_df)/total_accounts*100:.1f}%)")

    print("\n--- Flipping Profitability ---")
    print(f"  Profitable at Asking Price     : {len(profitable_ask):,} ({len(profitable_ask)/total_accounts*100:.1f}%)")
    print(f"  Profitable after Negotiation   : {len(profitable_neg):,} ({len(profitable_neg)/total_accounts*100:.1f}%)")

    if len(profitable_ask) > 0:
        print(f"  Avg Profit (at asking)         : {profitable_ask['profit_at_asking'].mean():,.0f} EGP")
        print(f"  Max Profit (at asking)         : {profitable_ask['profit_at_asking'].max():,.0f} EGP")

    if len(profitable_neg) > 0:
        print(f"  Avg Profit (negotiated)        : {profitable_neg['profit_negotiated'].mean():,.0f} EGP")
        print(f"  Max Profit (negotiated)        : {profitable_neg['profit_negotiated'].max():,.0f} EGP")
        print(f"  Total Potential Profit          : {profitable_neg['profit_negotiated'].sum():,.0f} EGP")

    print("\n--- Segment Breakdown ---")
    if len(economy) > 0:
        eco_mae = np.abs(economy['fair_value'] - economy['asking_price']).mean()
        eco_profit = economy[economy['profit_negotiated'] >= MIN_PROFIT_EGP]
        print(f"  Economy (<15k):  {len(economy):,} accounts | MAE: {eco_mae:,.0f} EGP | Profitable Deals: {len(eco_profit):,}")
    if len(whale) > 0:
        whale_mae = np.abs(whale['fair_value'] - whale['asking_price']).mean()
        whale_profit = whale[whale['profit_negotiated'] >= MIN_PROFIT_EGP]
        print(f"  Whale   (>=15k): {len(whale):,} accounts | MAE: {whale_mae:,.0f} EGP | Profitable Deals: {len(whale_profit):,}")

    # ─── Top 10 Best Deals ───────────────────────────────────
    if len(profitable_neg) > 0:
        print("\n--- Top 10 Best Sniper Deals (by Negotiated Profit) ---")
        top_deals = profitable_neg.nlargest(10, 'profit_negotiated')
        for rank, (_, d) in enumerate(top_deals.iterrows(), 1):
            print(f"  #{rank}: Ask {d['asking_price']:,.0f} | Fair {d['fair_value']:,.0f} | "
                  f"Buy@{d['negotiated_buy']:,.0f} -> Sell@{d['target_sell']:,.0f} | "
                  f"Profit: +{d['profit_negotiated']:,.0f} EGP")

    # ─── Save Report CSV ─────────────────────────────────────
    report_path = os.path.join('data', 'parsed', 'csv', 'backtest_results.csv')
    res_df.to_csv(report_path, index=False, encoding='utf-8-sig')
    print(f"\n[INFO] Full backtest results saved to: {report_path}")
    print("\n" + "=" * 60)
    print("  Backtest Complete!")
    print("=" * 60)

    return res_df


if __name__ == "__main__":
    run_backtest()
