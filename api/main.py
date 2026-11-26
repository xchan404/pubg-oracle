"""
PUBG Market Intelligence API
FastAPI application for evaluating accounts and providing market stats.
"""

import io
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'buffer') and 'pytest' not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')



from typing import Optional  # noqa: F401 - used in route signatures below

import uvicorn
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.deals_hub import hub
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
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()],
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


@app.get("/dashboard", include_in_schema=False)
def user_dashboard():
    """Subscriber dashboard (opened from inside the Telegram bot)."""
    return FileResponse(os.path.join(static_dir, "user.html"))


@app.get("/admin", include_in_schema=False)
def admin_dashboard():
    """Owner operations dashboard."""
    return FileResponse(os.path.join(static_dir, "admin.html"))


from api.dashboards import router as dashboards_router  # noqa: E402

app.include_router(dashboards_router)


# Load the model
pricer: EnsemblePricer | None = None
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
    if features.get("has_car_mclaren") or features.get("has_car_porsche") or features.get("has_car_dodge") or (features.get("cars_mythic") or 0) > 0:
        anchors.append({"name": "🏎️ Mythic Supercar (سيارة ميثك)", "tier": "A+", "icon": "🏎️"})
    if features.get("has_conqueror") or (features.get("conqueror_frames_count") or 0) > 0:
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
from intelligence.item_index import build_item_index, get_item_card
from intelligence.market_data import load_market_dataframe
from intelligence.repost_engine import get_listing_timeline, get_repost_summary
from intelligence.trends import MarketTrendsEngine
from intelligence.trust import compute_channel_trust

_trends = None
def _get_trends():
    global _trends
    if _trends is None:
        _trends = MarketTrendsEngine()
    return _trends

# ── Intelligence engines (Phase 2) — lazily built over the enriched dataset
_intel_cache: dict = {}

def _get_intel(name: str, builder):
    """Lazily computes and caches an intelligence artifact."""
    if name not in _intel_cache:
        _intel_cache[name] = builder(load_market_dataframe())
    return _intel_cache[name]

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


# ─── Intelligence Endpoints (Phase 2: dedup, item index, trust) ──────

@app.get("/market/reposts")
def get_repost_analytics():
    """Repost clusters, price trajectories, days-on-market and sold markers."""
    return _get_intel("reposts", get_repost_summary)


@app.get("/market/reposts/{fingerprint}")
def get_single_listing_timeline(fingerprint: str):
    """Full repost timeline for one account fingerprint."""
    return get_listing_timeline(load_market_dataframe(), fingerprint)


@app.get("/market/item-index")
def get_item_price_index(item: str | None = None):
    """
    Monthly hedonic price index per canonical item (EGP uplift vs comparable
    listings). Pass ?item=glacier_m416 for a single card.
    """
    index = _get_intel("item_index", build_item_index)
    if item:
        card = get_item_card(index, item)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Item not indexed: {item}")
        return card
    return {"items": index, "count": len(index)}


@app.get("/market/item-index/{item_id}")
def get_single_item_index(item_id: str):
    """Single-item hedonic price index card."""
    index = _get_intel("item_index", build_item_index)
    card = get_item_card(index, item_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Item not indexed: {item_id}")
    return card


@app.get("/market/channels/trust")
def get_channel_trust_ranking():
    """Trust scores per channel: scam signals, spam ratio, repost flooding."""
    def builder(df):
        result = compute_channel_trust(df)
        return result
    return _get_intel("trust", builder)


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


# ─── Health ──────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """Liveness probe: model loaded + data freshness (never raises)."""
    try:
        from intelligence.freshness import get_freshness
        data = get_freshness()
    except Exception as e:
        data = {"status": "unknown", "error": str(e)}
    return {"status": "ok", "model_loaded": pricer is not None, "data": data}


@app.get("/health/data")
def health_data():
    """Dedicated freshness probe for monitoring/alerting."""
    from intelligence.freshness import get_freshness

    return get_freshness()


# ─── Media (S3 presigned URLs) ───────────────────────────────
@app.get("/media/{key:path}")
def media_presigned_url(key: str, expiry: int = 300):
    """Return a short-lived presigned GET URL for an S3 object."""
    from services.s3_store import configured, generate_presigned_url

    if not configured():
        raise HTTPException(status_code=503, detail="S3 is not configured.")
    url = generate_presigned_url(key, expiry_seconds=max(60, min(expiry, 3600)))
    if not url:
        raise HTTPException(status_code=404, detail="Object not found or presign failed.")
    return {"key": key, "url": url, "expires_in": expiry}


# ─── Live Deals Feed (Phase 4) ───────────────────────────────
class DealPush(BaseModel):
    chat_title: str = ""
    message_link: str = ""
    asked_price: float | None = None
    fair_value: float
    profit: float | None = None
    segment: str = ""
    confidence_label: str = ""
    deal_rating: str = ""
    fingerprint: str = ""


@app.post("/internal/deal")
async def push_deal(deal: DealPush, x_internal_token: str | None = Header(default=None)):
    """Sniper bot pushes detected deals here; hub broadcasts to dashboards."""
    if hub.token_required() and not hub.token_valid(x_internal_token):
        raise HTTPException(status_code=401, detail="Invalid internal token")
    return hub.publish(deal.model_dump())


@app.get("/deals/recent")
def recent_deals(limit: int = 20):
    """Replay buffer of the latest pushed deals."""
    return {"deals": list(hub.recent)[: max(1, min(50, limit))]}


@app.websocket("/ws/deals")
async def ws_deals(ws: WebSocket):
    await hub.connect(ws)
    try:
        for deal in list(hub.recent)[:10]:
            await ws.send_json(deal)
        while True:
            # keepalive: consume pings/messages; broadcasts arrive async
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.disconnect(ws)


# ─── Portfolio Tracker (Phase 4) ─────────────────────────────
@app.get("/portfolio/summary")
def portfolio_summary():
    """Flipping P&L derived from bought/sold feedback labels."""
    from database.feedback import get_positions
    from intelligence.portfolio import build_portfolio_summary

    return build_portfolio_summary(get_positions())


# ─── Pricing Rules Admin (Phase 5 hot-reload) ────────────────
from ml.rules_engine import DEFAULT_RULES_PATH, validate_rules_text  # noqa: E402


def _write_rules(path, text):  # isolated for testability
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


@app.get("/rules")
def get_rules():
    """Current pricing rules (parsed) + the raw YAML text."""
    path = str(DEFAULT_RULES_PATH)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    rules, errors = validate_rules_text(text)
    return {"path": path, "rules": rules or {}, "validation_errors": errors}


@app.put("/rules")
async def put_rules(payload: dict):
    """
    Hot-reload pricing rules. Body: {"yaml_text": "..."}.
    Validates before writing; updates the live API pricer in place.
    (Bot process picks up changes on its next restart.)
    """
    yaml_text = (payload or {}).get("yaml_text", "")
    if not yaml_text.strip():
        raise HTTPException(status_code=400, detail="yaml_text is required")

    rules, errors = validate_rules_text(yaml_text)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    _write_rules(DEFAULT_RULES_PATH, yaml_text)

    # Hot-swap into every live engine instance in this process
    if pricer is not None and hasattr(pricer, "rules_engine"):
        pricer.rules_engine.rules = rules
        pricer.rules_engine.version = rules.get("version", 1)
    _intel_cache.pop("item_index", None)

    return {"status": "reloaded", "version": rules.get("version", 1)}
