"""
PUBG Market Intelligence API
FastAPI application for evaluating accounts and providing market stats.
"""

import io
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ml.pipeline import pipeline_instance
from ml.predict import EnsemblePricer

app = FastAPI(
    title="PUBG Market Intelligence API",
    description="API for account evaluation, market stats, and trends.",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
def root():
    """Serve the main dashboard."""
    return FileResponse(os.path.join(static_dir, "index.html"))


# Load the model
try:
    pricer = EnsemblePricer(models_dir='models')
except Exception as e:
    pricer = None
    print(f"Warning: Model not loaded: {e}")

import asyncio

import pandas as pd


class AccountRequest(BaseModel):
    text: str
    asking_price: float | None = None

CSV_DATASET_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'parsed', 'csv', 'all_parsed_accounts.csv')

def save_evaluated_account_to_dataset(features: dict):
    """Persists evaluated account into the CSV dataset to increment dataset counter in real-time."""
    try:
        if not os.path.exists(CSV_DATASET_PATH):
            return

        csv_columns = pd.read_csv(CSV_DATASET_PATH, nrows=0).columns.tolist()
        row_dict = {col: features.get(col, None) for col in csv_columns}
        row_dict["channel_username"] = "web_evaluator"
        row_dict["message_id"] = int(os.urandom(3).hex(), 16)

        row_df = pd.DataFrame([row_dict])
        row_df.to_csv(CSV_DATASET_PATH, mode='a', header=False, index=False)

        # Clear cache in trends engine to immediately update row count
        global _trends
        if _trends is not None:
            _trends._df = None

        print("[INFO] Successfully saved evaluated account to dataset CSV.")
    except Exception as e:
        print(f"[WARN] Could not save account to dataset: {e}")


def extract_anchor_highlights(features: dict) -> list:
    anchors = []
    if features.get("has_m4_glacier"):
        label = "🔥 M416 Glacier (امفور تلجي)"
        if features.get("m4_is_max"): label += " MAX"
        anchors.append({"name": label, "tier": "S+", "icon": "🔥"})
    if features.get("has_joker_fox"):
        label = "🦊 Joker Fox M416 (جوكر فوكس)"
        if features.get("has_joker_fox_locked"): label += " (مقفول مغلق)"
        anchors.append({"name": label, "tier": "S+", "icon": "🦊"})
    if features.get("has_mummy") or features.get("has_double_mummy"):
        label = "🧟 Mummy Outfit (المومياء)"
        if features.get("has_double_mummy"): label = "🧟 Double Mummy (مومياء مزدوجة)"
        anchors.append({"name": label, "tier": "S", "icon": "🧟"})
    if features.get("has_xsuit"):
        anchors.append({"name": "👑 X-Suit Outfit (بدلة اكس)", "tier": "S", "icon": "👑"})
    if features.get("has_face_girl"):
        anchors.append({"name": "👩 Girl Face & Hair (وش البنت الأصلي)", "tier": "A+", "icon": "👩"})
    if features.get("has_car_mclaren") or features.get("has_car_porsche") or features.get("has_car_dodge") or (features.get("cars_mythic") and features.get("cars_mythic") > 0):
        anchors.append({"name": "🏎️ Mythic Supercar (سيارة ميثك)", "tier": "A+", "icon": "🏎️"})
    if features.get("has_conqueror") or (features.get("conqueror_frames_count") and features.get("conqueror_frames_count") > 0):
        anchors.append({"name": "🏆 Conqueror Frame/Title (إطار كونكر)", "tier": "A", "icon": "🏆"})
    if features.get("has_lobby_mythic"):
        anchors.append({"name": "🏛️ Mythic Lobby (لوبي ميثك)", "tier": "A", "icon": "🏛️"})
    if features.get("has_scarf_tiger"):
        anchors.append({"name": "🐯 Tiger Scarf (اسكارف النمر)", "tier": "A", "icon": "🐯"})
    if features.get("has_soap_rare") or features.get("has_soap_double"):
        anchors.append({"name": "🧼 Rare Soap Set (الصابونة)", "tier": "B+", "icon": "🧼"})
    return anchors


@app.post("/evaluate")
async def evaluate_account(request: AccountRequest):
    if not pricer:
        raise HTTPException(status_code=503, detail="Pricing model is not available.")

    features = await asyncio.to_thread(pipeline_instance.process, request.text)

    # Save evaluated account into CSV dataset to increment dataset size counter
    await asyncio.to_thread(save_evaluated_account_to_dataset, features)

    asking_price = request.asking_price
    if asking_price is None and features.get("price_egp") and float(features["price_egp"]) > 0:
        asking_price = float(features["price_egp"])

    prediction = await asyncio.to_thread(pricer.predict, features, asking_price)

    # Extract security audit payload
    trust_score = features.get("trust_score", 70)
    risk_level = features.get("security_risk_level", "LOW")
    verdict_arabic = features.get("transferability_verdict", "حساب جيد ومقبول الأمان 🟢")
    verified_links = features.get("verified_links", [])
    warnings = features.get("risk_warnings", [])
    assurances = features.get("safety_assurances", [])
    precautions = features.get("recommended_precautions", [])

    detected_items = features.get("canonical_items", [])
    highlighted_anchors = extract_anchor_highlights(features)

    fair_val = prediction["fair_value_egp"]
    price_range = prediction.get("price_range", f"{int(fair_val*0.85):,} - {int(fair_val*1.15):,} EGP")

    deal_verdict = prediction.get("deal_verdict")
    deal_explanation = prediction.get("deal_explanation")

    if not deal_verdict and asking_price and asking_price > 0:
        if fair_val >= asking_price * 1.15:
            deal_verdict = "GREAT_DEAL"
            deal_explanation = f"صفقة ممتازة! التقييم ({fair_val:,.0f} ج.م) أعلى من سعر العرض ({asking_price:,.0f} ج.م) بنسبة {round((fair_val-asking_price)/asking_price*100)}%"
        elif fair_val >= asking_price * 0.85:
            deal_verdict = "FAIR_DEAL"
            deal_explanation = f"سعر عادل! التقييم ({fair_val:,.0f} ج.م) متوافق مع سعر العرض ({asking_price:,.0f} ج.م)"
        else:
            deal_verdict = "OVERPRICED"
            deal_explanation = f"سعر مبالغ فيه! التقييم ({fair_val:,.0f} ج.م) أقل من المطلوب ({asking_price:,.0f} ج.م)"
    elif not deal_verdict:
        deal_verdict = "FAIR_EVALUATION"
        deal_explanation = "تم التقييم بنجاح بناءً على عناصر الحساب واستراتيجيات التسعير"

    inventory = {
        "account_level": features.get("account_level", "N/A"),
        "collection_level": features.get("collection_level", "N/A"),
        "mythics_count": features.get("mythics_count", 0),
        "guns_count": features.get("guns_count", 0),
        "xsuits_count": features.get("xsuits_count", 0),
        "cars_total": features.get("cars_total", 0),
        "cars_mythic": features.get("cars_mythic", 0),
        "conqueror_frames": features.get("conqueror_frames_count", 0),
        "prestige_score": round(features.get("prestige_score", 0.0), 2),
        "combo_multiplier": round(features.get("combo_multiplier", 1.0), 2)
    }

    return {
        "fair_value_egp": fair_val,
        "price_range": price_range,
        "asking_price": asking_price,
        "segment": prediction.get("segment", "General Account"),
        "confidence": prediction.get("confidence", {"score": "85%", "label": "ثقة متوسطة"}),
        "detected_items": detected_items,
        "highlighted_anchors": highlighted_anchors,
        "inventory": inventory,
        "security": {
            "trust_score": trust_score,
            "risk_level": risk_level,
            "verdict_arabic": verdict_arabic,
            "verified_links": verified_links,
            "warnings": warnings,
            "assurances": assurances,
            "precautions": precautions,
            "signals": verified_links + assurances
        },
        "deal_verdict": deal_verdict,
        "deal_explanation": deal_explanation,
        "models_breakdown": prediction.get("models_breakdown", {})
    }


# ─── Market Trends & Analytics Endpoints ─────────────────────
from intelligence.trends import MarketTrendsEngine

_trends = None
def _get_trends():
    global _trends
    if _trends is None:
        _trends = MarketTrendsEngine()
    return _trends

@app.get("/market/summary")
def get_market_summary():
    """Returns high-level market overview: total listings, avg/median price, channel breakdown."""
    return _get_trends().get_market_summary()

@app.get("/market/prices")
def get_price_distribution():
    """Returns price distribution across budget/economy/mid/premium/whale segments."""
    return _get_trends().get_price_distribution()

@app.get("/market/items")
def get_item_frequency():
    """Returns item frequency counts and percentages across all listings."""
    return _get_trends().get_item_frequency()

@app.get("/market/m4")
def get_m4_distribution():
    """Returns M4 skin type distribution (Glacier, Joker, Aether, etc.)."""
    return _get_trends().get_m4_type_distribution()

@app.get("/market/impact")
def get_item_price_impact():
    """Returns price uplift analysis for each rare item."""
    return _get_trends().get_item_price_impact()

@app.get("/market/heatmap")
def get_rarity_demand_heatmap():
    """Returns rarity × demand heatmap with HOT/WARM/COOL signals."""
    return _get_trends().get_rarity_demand_heatmap()

@app.get("/market/trends")
def get_full_trends_report():
    """Returns the complete market trends report with all analytics."""
    return _get_trends().get_full_report()


# ─── MLOps Endpoints ────────────────────────
from ml.retrain_service import get_mlops_telemetry, run_retrain_service


@app.get("/mlops/status")
def get_mlops_status():
    """Returns dataset size, drift status (PSI score), training history, and MLOps metrics."""
    return get_mlops_telemetry()


@app.post("/mlops/retrain")
async def trigger_retrain():
    """Triggers automated model retraining via the retrain service."""
    try:
        await asyncio.to_thread(run_retrain_service, force=True)
        return {"status": "success", "message": "Model retraining triggered and completed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}") from e


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
