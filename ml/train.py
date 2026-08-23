import os

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import shap
import xgboost as xgb
from catboost import CatBoostRegressor
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split


def main():
    print("[INFO] Loading data from CSV...")
    csv_path = os.path.join("data", "parsed", "csv", "all_parsed_accounts.csv")
    df = pd.read_csv(csv_path, low_memory=False)

    # Step 1: Deep Data Cleaning
    df = df.dropna(subset=['price_egp', 'clean_text'])

    # 1. Filter out negotiation words that skew the price (Expanded)
    bad_words = r'راسلني|تفاوض|أو أقل|او اقل|أو أكتر|او اكتر|قابل للتفاوض|او يزيد|أو يزيد|تقريبا|تقريباً|حوالي|يبدأ من|ابتداء من'
    df = df[~df['clean_text'].str.contains(bad_words, case=False, na=False)].copy()

    # 2. Strict Price Boundaries (1,000 to 80,000)
    df = df[(df['price_egp'] >= 1000) & (df['price_egp'] <= 80000)].copy()

    print(f"[INFO] Total priced accounts for training: {len(df)}")

    # --- SYNTHETIC DATA AUGMENTATION ---
    print("[INFO] Generating Synthetic Data for Fluff Accounts...")
    import random
    synthetic_rows = []
    for _ in range(150):
        # Create a dummy row with default 0/None values for all columns in df
        row = {col: 0 for col in df.columns}
        row['clean_text'] = "synthetic fluff account high mythics no m4"

        # Fluff features (High numbers, NO M4)
        row['mythics_count'] = random.randint(45, 100)
        row['guns_count'] = random.randint(10, 25)
        row['account_level'] = random.randint(60, 85)
        row['collection_level'] = random.randint(40, 75)

        # Randomly assign secondary anchors
        if random.random() < 0.15: row['has_joker_fox'] = 1
        if random.random() < 0.15: row['has_mummy'] = 1
        if random.random() < 0.25: row['has_xsuit'] = 1
        if random.random() < 0.25: row['cars_mythic'] = random.randint(1, 3)
        if random.random() < 0.35: row['has_face_girl'] = 1

        # Assign a realistic low price based on anchors (imitating our old tiered logic)
        if row.get('has_joker_fox') or row.get('has_mummy'):
            row['price_egp'] = random.randint(2500, 3000)
        elif row.get('has_xsuit') or row.get('cars_mythic'):
            row['price_egp'] = random.randint(1800, 2200)
        elif row.get('has_face_girl'):
            row['price_egp'] = random.randint(1300, 1600)
        else:
            row['price_egp'] = random.randint(1000, 1200)

        synthetic_rows.append(row)

    synth_df = pd.DataFrame(synthetic_rows)
    df = pd.concat([df, synth_df], ignore_index=True)
    print(f"[INFO] Added 150 synthetic rows. Total accounts: {len(df)}")

    # Core Features to use
    features = [
        'account_level', 'collection_level', 'mythics_count', 'guns_count', 'xsuits_count',
        'm4_level', 'm4_is_max', 'cars_total', 'cars_mythic', 'has_airdrop_car',
        'conqueror_frames_count', 'has_conqueror_frame', 'has_plane_frame', 'has_re2_frame',
        'has_xsuit', 'has_m4_glacier', 'has_joker_fox', 'has_joker_fox_locked',
        'has_mummy', 'has_double_mummy', 'has_conqueror', 'has_vehicle_dev',
        'has_face_girl', 'has_lobby_mythic', 'has_car_mclaren', 'has_car_dodge',
        'has_ghazi', 'has_ghawas', 'has_soap_blue', 'has_soap_black', 'has_soap_rare',
        'has_soap_double', 'has_scarf_tiger', 'has_hair_qarnain', 'has_hair_kaboria', 'has_hair_yellow',
        'has_akm', 'akm_is_max', 'has_m762', 'm762_is_max', 'has_awm', 'awm_is_max',
        'has_uzi', 'uzi_is_max', 'has_ump', 'ump_is_max',
        'has_falcon', 'has_dog', 'has_cat', 'has_poro', 'has_penguin',
        'prestige_score', 'rarity_score', 'combo_multiplier',
        'has_m4_max_x_mummy', 'has_m4_x_xsuit', 'guns_per_mythic_ratio', 'has_super_combo'
    ]

    # One-hot encode m4_type if exists
    if 'm4_type' in df.columns:
        m4_dummies = pd.get_dummies(df['m4_type'], prefix='m4_type', dummy_na=True)
        df = pd.concat([df, m4_dummies], axis=1)
        features.extend(m4_dummies.columns.tolist())

    features = [f for f in features if f in df.columns]

    # Feature matrix X and target y
    df[features].copy().fillna(0).astype(float)
    np.log1p(df['price_egp'])

    # Split raw data into Train (85%) and Test (15%) FIRST to prevent any data leakage
    train_df, test_df = train_test_split(df, test_size=0.15, random_state=42)
    train_df = train_df.copy()
    test_df = test_df.copy()

    y_train_full = np.log1p(train_df['price_egp'])
    y_test_full = np.log1p(test_df['price_egp'])

    # --- FIT TRANSFORMERS STRICTLY ON TRAINING DATA TO PREVENT LEAKAGE ---
    print("[INFO] Vectorizing TF-IDF without Data Leakage (Fit on Train only)...")
    arabic_stopwords = ['للبيع', 'وسيط', 'جروب', 'تواصل', 'واتس', 'حساب', 'اكونت', 'السعر', 'سعر', 'ربط', 'في', 'من', 'على']
    vectorizer = TfidfVectorizer(max_features=100, ngram_range=(1, 2), stop_words=arabic_stopwords)

    tfidf_train_mat = vectorizer.fit_transform(train_df['clean_text'].fillna(''))
    tfidf_test_mat = vectorizer.transform(test_df['clean_text'].fillna(''))

    tfidf_cols = [f'tfidf_{i}' for i in range(100)]
    tfidf_train_df = pd.DataFrame(tfidf_train_mat.toarray(), index=train_df.index, columns=tfidf_cols)
    tfidf_test_df = pd.DataFrame(tfidf_test_mat.toarray(), index=test_df.index, columns=tfidf_cols)

    X_base_train = train_df[features].copy().fillna(0).astype(float)
    X_base_test = test_df[features].copy().fillna(0).astype(float)

    # --- K-MEANS CLUSTERING ---
    print("[INFO] Performing K-Means Clustering on Train Base Features...")
    kmeans = KMeans(n_clusters=8, random_state=42, n_init='auto')
    train_clusters = kmeans.fit_predict(X_base_train)
    test_clusters = kmeans.predict(X_base_test)

    cluster_train_df = pd.DataFrame(index=train_df.index)
    cluster_test_df = pd.DataFrame(index=test_df.index)
    for i in range(8):
        col_name = f'cluster_{i}'
        cluster_train_df[col_name] = (train_clusters == i).astype(float)
        cluster_test_df[col_name] = (test_clusters == i).astype(float)

    X_train = pd.concat([X_base_train, tfidf_train_df, cluster_train_df], axis=1)
    X_test = pd.concat([X_base_test, tfidf_test_df, cluster_test_df], axis=1)

    y_train = y_train_full
    y_test = y_test_full
    all_features = X_train.columns.tolist()

    # Split dataset into Cheap (< 15k) and Expensive (>= 15k) for train and test sets
    print("[INFO] Segmenting train and test sets into Cheap (< 15k) and Expensive (>= 15k)...")
    mask_cheap_train = train_df['price_egp'] < 15000
    mask_cheap_test = test_df['price_egp'] < 15000

    mask_exp_train = train_df['price_egp'] >= 15000
    mask_exp_test = test_df['price_egp'] >= 15000

    X_train_cheap, y_train_cheap = X_train[mask_cheap_train], y_train[mask_cheap_train]
    X_test_cheap, y_test_cheap = X_test[mask_cheap_test], y_test[mask_cheap_test]

    X_train_exp, y_train_exp = X_train[mask_exp_train], y_train[mask_exp_train]
    X_test_exp, y_test_exp = X_test[mask_exp_test], y_test[mask_exp_test]

    # --- STEP 3: OPTUNA HYPERPARAMETER TUNING (5-FOLD CV) ---
    print(f"\n[INFO] Optuna Tuning (5-Fold CV) for LightGBM on Cheap Segment (< 15k)... (Train: {len(X_train_cheap)}, Test: {len(X_test_cheap)})")

    from sklearn.model_selection import KFold

    def objective_lgb(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 300, 2000),
            'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.05, log=True),
            'max_depth': trial.suggest_int('max_depth', 4, 12),
            'num_leaves': trial.suggest_int('num_leaves', 15, 80),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'objective': 'mae',
            'random_state': 42,
            'n_jobs': -1,
            'verbose': -1
        }
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        scores = []
        for tr_idx, va_idx in kf.split(X_train_cheap):
            X_tr, y_tr = X_train_cheap.iloc[tr_idx], y_train_cheap.iloc[tr_idx]
            X_va, y_va = X_train_cheap.iloc[va_idx], y_train_cheap.iloc[va_idx]
            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_va, y_va)],
                callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
            )
            preds = np.expm1(model.predict(X_va))
            actuals = np.expm1(y_va)
            scores.append(mean_absolute_error(actuals, preds))
        return float(np.mean(scores))

    study_lgb = optuna.create_study(direction='minimize')
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study_lgb.optimize(objective_lgb, n_trials=15)

    print(f"Best LightGBM Params: {study_lgb.best_params}")
    best_lgb_params = study_lgb.best_params
    best_lgb_params.update({'objective': 'mae', 'random_state': 42, 'n_jobs': -1, 'verbose': -1})

    lgb_model = lgb.LGBMRegressor(**best_lgb_params)
    lgb_model.fit(
        X_train_cheap, y_train_cheap,
        eval_set=[(X_test_cheap, y_test_cheap)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )

    print(f"\n[INFO] Training XGBoost on Expensive Segment (>= 15k)... (Train: {len(X_train_exp)}, Test: {len(X_test_exp)})")

    xgb_model = xgb.XGBRegressor(
        n_estimators=1500,
        learning_rate=0.02,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:absoluteerror',
        random_state=42,
        n_jobs=-1,
        early_stopping_rounds=50
    )
    xgb_model.fit(
        X_train_exp, y_train_exp,
        eval_set=[(X_test_exp, y_test_exp)],
        verbose=False
    )

    print("\n[INFO] Evaluating models on their respective segments...")

    # Cheap Evaluation
    lgb_preds_log = lgb_model.predict(X_test_cheap)
    lgb_preds = np.expm1(lgb_preds_log)
    actuals_cheap = np.expm1(y_test_cheap)
    mae_cheap = mean_absolute_error(actuals_cheap, lgb_preds)

    # Expensive Evaluation
    xgb_preds_log = xgb_model.predict(X_test_exp)
    xgb_preds = np.expm1(xgb_preds_log)
    actuals_exp = np.expm1(y_test_exp)
    mae_exp = mean_absolute_error(actuals_exp, xgb_preds)

    # Overall Evaluation (Combined)
    overall_mae = (mae_cheap * len(actuals_cheap) + mae_exp * len(actuals_exp)) / (len(actuals_cheap) + len(actuals_exp))

    print("\n[INFO] Training CatBoost on Overall Dataset (Blended Mode)...")
    cat_model = CatBoostRegressor(
        iterations=1500,
        learning_rate=0.03,
        depth=6,
        loss_function='MAE',
        random_seed=42,
        verbose=0,
        early_stopping_rounds=50
    )
    cat_model.fit(X_train, y_train, eval_set=(X_test, y_test))

    cat_preds_log = cat_model.predict(X_test)
    cat_preds = np.expm1(cat_preds_log)
    actuals = np.expm1(y_test)
    mean_absolute_error(actuals, cat_preds)

    print("\n--- FINAL ENSEMBLE PERFORMANCE ---")
    print(f"   < 15k   (LightGBM) MAE: {mae_cheap:.2f} EGP")
    print(f"   >= 15k  (XGBoost)  MAE: {mae_exp:.2f} EGP")
    print(f"   Overall Blended    MAE: {overall_mae:.2f} EGP")
    print("\n[INFO] Training Empirical Quantile Regressors (q10 & q90)...")
    q10_model = lgb.LGBMRegressor(
        objective='quantile',
        alpha=0.10,
        n_estimators=800,
        learning_rate=0.03,
        random_state=42,
        n_jobs=-1,
        verbose=-1
    )
    q10_model.fit(X_train, y_train)

    q90_model = lgb.LGBMRegressor(
        objective='quantile',
        alpha=0.90,
        n_estimators=800,
        learning_rate=0.03,
        random_state=42,
        n_jobs=-1,
        verbose=-1
    )
    q90_model.fit(X_train, y_train)

    print("\n[INFO] Saving models...")
    os.makedirs('models', exist_ok=True)
    joblib.dump(xgb_model, os.path.join('models', 'pubg_pricer_xgb.pkl'))
    joblib.dump(lgb_model, os.path.join('models', 'pubg_pricer_lgb.pkl'))
    joblib.dump(cat_model, os.path.join('models', 'pubg_pricer_cat.pkl'))
    joblib.dump(q10_model, os.path.join('models', 'pubg_pricer_q10.pkl'))
    joblib.dump(q90_model, os.path.join('models', 'pubg_pricer_q90.pkl'))
    joblib.dump(kmeans, os.path.join('models', 'kmeans_clusterer.pkl'))
    joblib.dump(all_features, os.path.join('models', 'model_features.pkl'))
    joblib.dump(vectorizer, os.path.join('models', 'tfidf_vectorizer.pkl'))

    print("\n[INFO] Calculating SHAP values for XGBoost (Feature Isolation)...")
    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_train)

    # Average absolute SHAP value per feature
    np.abs(shap_values).mean(axis=0)

    # Baseline price is the exponent of the expected value of the explainer
    baseline_price = np.expm1(explainer.expected_value)
    if isinstance(baseline_price, np.ndarray):
        baseline_price = baseline_price[0]

    isolated_impacts = {}

    for i, feature in enumerate(all_features):
        # We only care about our original boolean features for the report, not TF-IDF
        if feature.startswith('tfidf_') or feature == 'clean_text':
            continue

        # Filter SHAP values where the feature is present (> 0)
        present_mask = X_train[feature] > 0
        if present_mask.sum() > 5:  # Need at least 5 examples to estimate impact
            # What does this feature add to the price when it's present?
            # Mean SHAP value (log scale)
            log_impact = shap_values[present_mask, i].mean()
            # EGP impact = (e^log_impact - 1) * baseline_price
            egp_impact = (np.exp(log_impact) - 1) * baseline_price
            isolated_impacts[feature] = egp_impact

    # We skip printing SHAP values here as we focus on Ensemble Performance in this step
    print("\n[INFO] Done!")

if __name__ == '__main__':
    main()
