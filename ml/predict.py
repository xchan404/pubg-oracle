import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

from parser.regex_parser import parse_account_data
from ml.pipeline import pipeline_instance

class EnsemblePricer:
    def __init__(self, models_dir='models'):
        self.xgb_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_xgb.pkl'))
        self.lgb_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_lgb.pkl'))
        self.cat_model = joblib.load(os.path.join(models_dir, 'pubg_pricer_cat.pkl'))
        self.kmeans = joblib.load(os.path.join(models_dir, 'kmeans_clusterer.pkl'))
        self.features = joblib.load(os.path.join(models_dir, 'model_features.pkl'))
        self.vectorizer = joblib.load(os.path.join(models_dir, 'tfidf_vectorizer.pkl'))

        # Quantile Models for empirical bounds
        q10_path = os.path.join(models_dir, 'pubg_pricer_q10.pkl')
        q90_path = os.path.join(models_dir, 'pubg_pricer_q90.pkl')
        self.q10_model = joblib.load(q10_path) if os.path.exists(q10_path) else None
        self.q90_model = joblib.load(q90_path) if os.path.exists(q90_path) else None

    def predict(self, account_data, asking_price: float = None) -> dict:
        """
        Takes a dictionary of account features OR a raw text string, and an optional asking price.
        Returns the predicted fair value and arbitrage negotiation details.
        """
        if isinstance(account_data, str):
            account_data = pipeline_instance.process(account_data)
            
        # Convert to DataFrame
        df = pd.DataFrame([account_data])
        
        # Ensure all columns exist
        for col in self.features:
            if col not in df.columns and not col.startswith('tfidf_') and not col.startswith('cluster_'):
                df[col] = 0
                
        # Handle TF-IDF
        text = str(df['clean_text'].iloc[0]) if 'clean_text' in df.columns else ''
        tfidf_features = self.vectorizer.transform([text]).toarray()
        
        # Build the initial feature vector
        X_dict = {}
        for col in self.features:
            if col.startswith('tfidf_'):
                idx = int(col.split('_')[1])
                X_dict[col] = tfidf_features[0][idx]
            elif not col.startswith('cluster_'):
                X_dict[col] = df[col].iloc[0] if col in df.columns else 0
        
        # Predict Cluster
        base_features = [f for f in self.features if not f.startswith('tfidf_') and not f.startswith('cluster_')]
        base_df = pd.DataFrame([X_dict])[base_features].astype(float).fillna(0.0)
        cluster_id = self.kmeans.predict(base_df)[0]
        
        # Add Cluster Dummy Features
        for i in range(8):
            X_dict[f'cluster_{i}'] = 1 if i == cluster_id else 0
            
        # Reorder to match model
        X = pd.DataFrame([X_dict])[self.features].astype(float).fillna(0)
        
        # Predict in log scale
        xgb_pred_log = self.xgb_model.predict(X)[0]
        lgb_pred_log = self.lgb_model.predict(X)[0]
        cat_pred_log = self.cat_model.predict(X)[0]
        
        # Convert back to EGP
        xgb_price = np.expm1(xgb_pred_log)
        lgb_price = np.expm1(lgb_pred_log)
        cat_price = np.expm1(cat_pred_log)

        # Quantile predictions
        q10_price = np.expm1(self.q10_model.predict(X)[0]) if self.q10_model else None
        q90_price = np.expm1(self.q90_model.predict(X)[0]) if self.q90_model else None
        
        # Calculate Average to determine segment
        avg_price = (xgb_price + lgb_price + cat_price) / 3
        
        # Note: XGBoost proved to be significantly stronger during training for whales,
        # CatBoost is great overall, LightGBM is best for cheap accounts.
        if lgb_price < 15000:
            # For cheap accounts, blend LightGBM and CatBoost
            final_price = (lgb_price * 0.6) + (cat_price * 0.4)
            segment = "Economy/Mid-Tier (<15k)"
            confidence_margin = 1200 # Based on test MAE for cheap
        else:
            # For expensive accounts, blend XGBoost and CatBoost
            final_price = (xgb_price * 0.7) + (cat_price * 0.3)
            segment = "Whale/Expensive (>=15k)"
            confidence_margin = 3200 # Based on test MAE for high end
            
        fair_value = round(final_price)
        
        # --- NEW: Hard Ceiling Business Rule (No M4/Anchors = Max 1000) ---
        has_m4 = False
        if 'm4_type' in df.columns and df['m4_type'].iloc[0] not in [None, 0, '0']: has_m4 = True
        if 'm4_level' in df.columns and df['m4_level'].iloc[0] is not None and df['m4_level'].iloc[0] > 0: has_m4 = True
        if 'm4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1: has_m4 = True
        
        has_xsuit = ('has_xsuit' in df.columns and df['has_xsuit'].iloc[0] == 1)
        has_joker_fox = ('has_joker_fox' in df.columns and df['has_joker_fox'].iloc[0] == 1)
        has_mummy = ('has_mummy' in df.columns and df['has_mummy'].iloc[0] == 1)
        has_mummy_helmet = ('has_mummy_helmet' in df.columns and df['has_mummy_helmet'].iloc[0] == 1)

        has_mythic_car = False
        if 'cars_mythic' in df.columns and df['cars_mythic'].iloc[0] is not None and df['cars_mythic'].iloc[0] > 0: has_mythic_car = True
        if 'has_car_mclaren' in df.columns and df['has_car_mclaren'].iloc[0] == 1: has_mythic_car = True
        if 'has_car_dodge' in df.columns and df['has_car_dodge'].iloc[0] == 1: has_mythic_car = True
        if 'rare_items_str' in df.columns:
            rare_str = str(df['rare_items_str'].iloc[0])
            if 'car_' in rare_str and 'car_dev_fleet' not in rare_str:
                has_mythic_car = True

        has_girl_face = ('has_face_girl' in df.columns and df['has_face_girl'].iloc[0] == 1)
        import re
        raw_text = str(df['clean_text'].iloc[0]) if 'clean_text' in df.columns else ""
        
        # --- NEW: Ultra Rares Premium Calculation ---
        # Only add explicit premiums for items that drastically break the ML model's baseline (the "Unicorns").
        rare_premium = 0
        
        # Joker Fox Closed (Open is handled fine by ML base)
        if has_joker_fox:
            if 'has_joker_fox_locked' in df.columns and df['has_joker_fox_locked'].iloc[0] == 1:
                rare_premium += 1500 
            elif re.search(r'مقفول', raw_text):
                rare_premium += 1500
                
        # Mummy Helmet (Inferno Rider / Hell Helmet) - Matches Joker Fox value!
        if has_mummy_helmet: 
            rare_premium += 1500
            
        # Upgraded X-Suits (Kill/Max/Level 4+)
        if has_xsuit:
            if re.search(r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x|xsuit)[\s\S]{0,30}?(?:كيل|ماكس|لفل\s*[4-7]|level\s*[4-7])', raw_text, re.IGNORECASE):
                rare_premium += 1500
            elif re.search(r'(?:الغراب|فرعون|بوسايدون|سيلفانوس|انوبيس|الجوكر|الموميا|لفينكيسترا)[\s\S]{0,30}?(?:كيل|ماكس|لفل\s*[4-7])', raw_text, re.IGNORECASE):
                rare_premium += 1500
            
        # Frames (Only Gold/Silver/2018 are expensive but lost value recently without M4)
        if 'has_plane_frame' in df.columns and df['has_plane_frame'].iloc[0] == 1:
            if re.search(r'فضي|ذهبي|دهبي|2018', raw_text):
                rare_premium += 500
        elif re.search(r'طيار', raw_text, re.IGNORECASE):
            if re.search(r'فضي|ذهبي|دهبي|2018', raw_text):
                rare_premium += 500
                
        # RE2 / Godzilla Frames
        if 'has_re2_frame' in df.columns and df['has_re2_frame'].iloc[0] == 1:
            rare_premium += 300
        elif re.search(r're2|جودزيلا', raw_text, re.IGNORECASE):
            rare_premium += 300

        # Old Seasons Avatars/Conquerors (S2/S3 specific)
        if re.search(r'حاصد|متسلق|s2\b|s3\b|الموسم\s*(?:التاني|الثاني)', raw_text, re.IGNORECASE):
            rare_premium += 1500

                # Secondary Ultra Rares (Hair, Faces, Outfits, Scarfs)
        if re.search(r'فيس\s*بنت|فيس\s*البنت', raw_text, re.IGNORECASE):
            rare_premium += 500
        if re.search(r'شعر\s*القرنين', raw_text, re.IGNORECASE):
            rare_premium += 300
        if re.search(r'صابونه\s*زرقا|الصابونه\s*الزرقا', raw_text, re.IGNORECASE):
            rare_premium += 300
        if re.search(r'وشاح\s*النمر', raw_text, re.IGNORECASE):
            rare_premium += 200
        if re.search(r'كابوريا|الكابوريا', raw_text, re.IGNORECASE):
            rare_premium += 200
        if re.search(r'بدلة\s*جولد|راس\s*جولد', raw_text, re.IGNORECASE):
            rare_premium += 400
        if re.search(r'شنطة\s*الغراب|شنطه\s*الغراب', raw_text, re.IGNORECASE):
            rare_premium += 300
            
        # Mythic Cars
        if has_mythic_car:
            car_count = int(df['cars_mythic'].iloc[0]) if 'cars_mythic' in df.columns and pd.notna(df['cars_mythic'].iloc[0]) else 1
            rare_premium += (1500 + (max(0, car_count - 1) * 1000))

        # Add the premium to the ML base fair value
        fair_value += rare_premium

        # Calculate extra premiums for raw stats (Guns/Mythics)
        guns_val = int(df['guns_count'].iloc[0]) if 'guns_count' in df.columns and pd.notna(df['guns_count'].iloc[0]) else 0
        mythics_val = int(df['mythics_count'].iloc[0]) if 'mythics_count' in df.columns and pd.notna(df['mythics_count'].iloc[0]) else 0
        
        extra_premium = rare_premium
        if 'm4_level' in df.columns and pd.notna(df['m4_level'].iloc[0]):
            m4_lvl = df['m4_level'].iloc[0]
            if m4_lvl == 4: extra_premium += 500
            elif m4_lvl > 4 and ('m4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 0): extra_premium += 800
            elif 'm4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1: extra_premium += 1500
            
        if mythics_val >= 100: extra_premium += 1000
        elif mythics_val >= 70: extra_premium += 500
        elif mythics_val >= 50: extra_premium += 300
        
        if guns_val >= 30: extra_premium += 1500
        elif guns_val >= 15: extra_premium += 500

        # Apply Tiered Caps based on M4 presence
        if not has_m4:
            if extra_premium >= 2500:
                cap = 3500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap: 
                    segment = "Capped: Ultra Rares (No M4)"
                    confidence_margin = 800
            elif extra_premium > 0:
                cap = 1500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap: 
                    segment = "Capped: Rare Items (No M4)"
                    confidence_margin = 600
            elif has_joker_fox or has_mummy:
                # Basic open joker or normal mummy
                cap = 2000
                fair_value = min(fair_value, cap)
                if fair_value <= cap: 
                    segment = "Capped: Joker/Mummy Only (Dynamic)"
                    confidence_margin = 400
            elif has_xsuit or has_mythic_car:
                cap = 1500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: X-Suit/Mythic Car Only (Dynamic)"
                    confidence_margin = 300
            elif has_girl_face:
                cap = 1000 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: Girl Face Only (Dynamic)"
                    confidence_margin = 250
            else:
                cap = 500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: No Anchors (Dynamic)"
                    confidence_margin = 200
        else:
            m4_lvl = df['m4_level'].iloc[0] if 'm4_level' in df.columns and pd.notna(df['m4_level'].iloc[0]) else 1
            is_max = ('m4_is_max' in df.columns and df['m4_is_max'].iloc[0] == 1) or (m4_lvl >= 7)
            
            if is_max:
                # Max M4 Account
                cap = 5000 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: Max M4 + Anchors (Dynamic)"
                    confidence_margin = 800
            elif m4_lvl == 4:
                # Kill Message M4 Account
                cap = 2500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: Kill Msg M4 (Lvl 4) + Anchors (Dynamic)"
                    confidence_margin = 500
            elif m4_lvl > 4:
                cap = 3500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: High Lvl M4 + Anchors (Dynamic)"
                    confidence_margin = 600
            else:
                # Basic M4 Account
                cap = 1500 + extra_premium
                fair_value = min(fair_value, cap)
                if fair_value <= cap:
                    segment = "Capped: Basic M4 + Anchors (Dynamic)"
                    confidence_margin = 300
                
                # --- NEW: Multiple M4s Premium ---
        m4_count = account_data.get('m4_count', 1) if isinstance(account_data, dict) else 1
        
        if m4_count > 1:
            segment = "Premium: Double M4"
            
            for i in range(2, m4_count + 1):
                suffix = f'_{i}' if i > 1 else ''
                m4_is_max = account_data.get(f'm4{suffix}_is_max', False) if isinstance(account_data, dict) else False
                m4_lvl = account_data.get(f'm4{suffix}_level') if isinstance(account_data, dict) else 1
                if m4_lvl is None: m4_lvl = 1
                
                if m4_is_max or m4_lvl >= 7:
                    fair_value += 2500
                    if i == 2: segment += " (+Max)"
                elif m4_lvl >= 4:
                    fair_value += 1500
                    if i == 2: segment += " (+Kill Msg)"
                else:
                    fair_value += 800
                    if i == 2: segment += " (+Basic)"
            
            if m4_count > 2:
                segment = segment.replace("Double", "Triple")
                
        # --- NEW: Confidence Score Calculation ---
        # Base confidence starts high, drops for expensive accounts (due to low training data)
        # and drops further if there are multiple rare items (high variance).
        confidence_score = 95
        if final_price >= 15000:
            confidence_score -= 25
        elif final_price >= 8000:
            confidence_score -= 10
            
        # Penalize for rare/volatile items
        rare_items = 0
        if 'has_mummy' in df.columns: 
            rare_items += int(df['has_mummy'].iloc[0] or 0)
        if 'has_xsuit' in df.columns: 
            rare_items += int(df['has_xsuit'].iloc[0] or 0)
        if 'cars_mythic' in df.columns: 
            rare_items += min(2, int(df['cars_mythic'].iloc[0] or 0))
        
        confidence_score -= (rare_items * 4)
        confidence_score = max(40, min(99, confidence_score)) # Clamp between 40-99
        
        if confidence_score >= 85:
            conf_label = "🟢 ثقة عالية (الموديل متأكد جداً من السعر)"
        elif confidence_score >= 70:
            conf_label = "🟡 ثقة متوسطة (السعر تقريبي، قد يختلف قليلاً)"
        else:
            conf_label = "🔴 ثقة منخفضة (الحساب نادر/غالي والداتا قليلة، يحتاج تقييم بشري للإضافة)"
        
        model_was_overridden = (not has_m4) and (round(final_price) != fair_value)

        # Calculate empirical price bounds
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
            "confidence": {
                "score": f"{confidence_score}%",
                "label": conf_label
            },
            "models_breakdown": {
                "xgboost_estimate": int(xgb_price),
                "lightgbm_estimate": int(lgb_price),
                "catboost_estimate": int(cat_price),
                "note": "⚠️ القيمة النهائية اتعدلت بواسطة Business Rules (السقف السعري)" if model_was_overridden else "✅ القيمة النهائية مباشرة من الموديل"
            }
        }
        
        # Arbitrage / Flipping Engine Logic
        if asking_price is not None:
            # 1. Dynamic Margins based on the Appraised Fair Value
            if fair_value < 3000:
                # Cheap accounts need a larger % or flat margin to be worth the effort
                buy_discount = 0.30  # 30% discount
                sell_premium = 0.15  # 15% markup
            elif fair_value < 15000:
                # Mid-tier accounts
                buy_discount = 0.20  # 20% discount
                sell_premium = 0.10  # 10% markup
            else:
                # Whale accounts - smaller % but large absolute cash
                buy_discount = 0.15  # 15% discount
                sell_premium = 0.10  # 10% markup
                
            target_buy = int(fair_value * (1 - buy_discount))
            target_sell = int(fair_value * (1 + sell_premium))
            
            profit_at_asking = target_sell - asking_price
            profit_if_negotiated = target_sell - target_buy

            # 3. Deal Rating
            if asking_price <= target_buy:
                rating = "🔥🔥 لقطة ممتازة! (اشترِ فوراً)"
            elif asking_price <= fair_value:
                rating = "👍 سعر عادل (حاول تنزل السعر لضمان ربح)"
            else:
                rating = "❌ غالي جداً (تجاوزه)"
                
            result["flipping_advice"] = {
                "deal_rating": rating,
                "asking_price": asking_price,
                "target_buy_price": target_buy,
                "target_sell_price": target_sell,
                "profit_if_bought_at_asking": profit_at_asking,
                "profit_if_negotiated": profit_if_negotiated,
                "negotiation_gain": profit_if_negotiated - profit_at_asking
            }
            
        return result

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    pricer = EnsemblePricer()
    
    # Test 1: Empty Account (Should be low)
    test_1 = {}
    
    # Test 2: M4 Max Account
    test_2 = {'m4_level': 7, 'm4_is_max': 1, 'has_m4_glacier': 1, 'account_level': 70, 'guns_count': 1}
    
    # Test 3: Whale Account with an Asking Price of 9000
    test_3 = {
        'cars_total': 5, 'has_mummy': 1, 'has_car_mclaren': 1, 'm4_level': 7, 'm4_is_max': 1,
        'has_m4_glacier': 1, 'mythics_count': 50, 'account_level': 85,
        'has_akm': 1, 'akm_is_max': 1, 'has_falcon': 1
    }
    
    print("--- ARBITRAGE PREDICTIONS TEST ---")
    print("\n1. Empty Account:")
    print(pricer.predict(test_1))
    
    print("\n2. M4 Max Account:")
    print(pricer.predict(test_2))
    
    print("\n3. Whale Account (Asking 9000 EGP):")
    import json
    print(json.dumps(pricer.predict(test_3, asking_price=9000), indent=2, ensure_ascii=False))
