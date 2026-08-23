import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pipeline.ensemble_predict import EnsemblePricer

st.set_page_config(
    page_title="PUBG Flipping Engine",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;800&display=swap');

    html, body, #root, .stApp, [class*="css"] {
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }

    .stApp {
        background: radial-gradient(circle at top right, #1a1a2e 0%, #16213e 50%, #0f3460 100%) !important;
        color: white !important;
    }

    /* All labels and text right-aligned */
    label, p, div, span, h1, h2, h3, h4 {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Tajawal', sans-serif !important;
    }

    h1 { color: #e94560 !important; font-weight: 800 !important; }
    h2, h3 { color: #fca311 !important; }

    /* Textarea & number input */
    textarea, input[type="number"] {
        background-color: rgba(255,255,255,0.08) !important;
        color: white !important;
        border: 1px solid #e94560 !important;
        border-radius: 10px !important;
        font-family: 'Tajawal', sans-serif !important;
        direction: rtl !important;
    }

    /* Button */
    .stButton > button {
        background: linear-gradient(90deg, #e94560 0%, #ff4b2b 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-size: 1.2rem !important;
        font-weight: bold !important;
        width: 100% !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    .stButton > button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 0 15px rgba(233,69,96,0.6) !important;
    }

    /* Custom HTML Cards */
    .card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 15px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .card-title {
        color: #fca311;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 16px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 8px;
    }
    .metrics-row {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        direction: rtl;
    }
    .metric-box {
        flex: 1;
        min-width: 150px;
        background: rgba(255,255,255,0.07);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .metric-label {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.6);
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #00d2ff;
    }
    .metric-value.green  { color: #00e676; }
    .metric-value.red    { color: #ff5252; }
    .metric-value.yellow { color: #ffd740; }

    .rating-badge {
        display: inline-block;
        padding: 10px 20px;
        border-radius: 10px;
        font-size: 1.2rem;
        font-weight: 800;
        margin-bottom: 16px;
        width: 100%;
        text-align: center;
    }
    .rating-fire   { background: rgba(255, 87, 34, 0.25); border: 1px solid #ff5722; color: #ff8a65; }
    .rating-ok     { background: rgba(255, 193, 7, 0.2);  border: 1px solid #ffc107; color: #ffd54f; }
    .rating-bad    { background: rgba(244, 67, 54, 0.2);  border: 1px solid #f44336; color: #ef9a9a; }

    .profit-positive { color: #00e676; font-size: 1.4rem; font-weight: 800; }
    .profit-negative { color: #ff5252; font-size: 1.4rem; font-weight: 800; }
    .profit-warning  {
        background: rgba(255,82,82,0.15);
        border: 1px solid #ff5252;
        border-radius: 10px;
        padding: 12px;
        color: #ff8a80;
        font-weight: 600;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- Initialize Model ---
@st.cache_resource
def load_pricer():
    return EnsemblePricer()

try:
    pricer = load_pricer()
    model_loaded = True
except Exception as e:
    st.error(f"❌ خطأ في تحميل الموديل: {str(e)}")
    model_loaded = False

# --- Header ---
st.title("🔥 محرك صفقات ببجي (PUBG Arbitrage Engine)")
st.markdown("##### المساعد الذكي لتقييم الحسابات واصطياد اللقطات")
st.markdown("---")

# --- Input Section ---
st.markdown("##### 📝 تفاصيل الحساب المعروض")
col1, col2 = st.columns([3, 1])

with col1:
    account_text = st.text_area(
        "انسخ بوست البائع هنا:",
        height=150,
        placeholder="مثال: امفور جوكر ماكس، 3 اكس سوت، موميا بيضا، مكلارين..."
    )

with col2:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    asking_price = st.number_input("السعر المطلوب (ج.م):", min_value=0, value=0, step=500)

if asking_price == 0:
    asking_price = None

analyze_btn = st.button("🚀 حلل وقيم الأكونت")

st.markdown("---")

# --- Results Section ---
if analyze_btn and account_text and model_loaded:
    with st.spinner("جاري تشغيل الذكاء الاصطناعي..."):
        result = pricer.predict(account_text, asking_price)

    conf  = result.get('confidence', {})
    fv    = result['fair_value_egp']
    seg   = result['segment']
    rng   = result['price_range']
    cscore = conf.get('score', 'N/A')
    clabel = conf.get('label', '')

    # --- Fair Value Card ---
    st.markdown(f"""
    <div class="card">
        <div class="card-title">💰 التقييم العادل للمحرك</div>
        <div class="metrics-row">
            <div class="metric-box">
                <div class="metric-label">القيمة العادلة (Fair Value)</div>
                <div class="metric-value">{fv:,} ج.م</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">النطاق السعري</div>
                <div class="metric-value" style="font-size:1.1rem">{rng}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">درجة الثقة</div>
                <div class="metric-value yellow">{cscore}</div>
                <div style="font-size:0.8rem; color:rgba(255,255,255,0.5); margin-top:4px">{clabel}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">الشريحة</div>
                <div class="metric-value" style="font-size:1rem; color:#ce93d8">{seg}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Models Breakdown Card ---
    bd = result.get('models_breakdown', {})
    if bd:
        xgb = bd.get('xgboost_estimate', 0)
        lgb = bd.get('lightgbm_estimate', 0)
        note = bd.get('note', '')
        
        st.markdown(f"""
        <div class="card" style="padding: 16px; margin-bottom: 20px;">
            <div class="metric-label" style="margin-bottom:8px">🔍 كواليس التقييم (Models Breakdown):</div>
            <div style="display:flex; gap: 20px; font-size: 0.95rem; color: #b2ebf2; direction: rtl;">
                <div><strong>XGBoost:</strong> {xgb:,} ج.م</div>
                <div><strong>LightGBM:</strong> {lgb:,} ج.م</div>
            </div>
            <div style="font-size: 0.85rem; color: #ffcc80; margin-top: 8px;">{note}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- Flipping Advice Card ---
    if "flipping_advice" in result:
        advice = result["flipping_advice"]
        rating = advice['deal_rating']
        profit_at_asking = advice['profit_if_bought_at_asking']
        profit_negotiated = advice['profit_if_negotiated']
        gain = advice['negotiation_gain']
        target_buy  = advice['target_buy_price']
        target_sell = advice['target_sell_price']
        ask         = advice['asking_price']

        # Rating style
        if "لقطة" in rating:
            rating_class = "rating-fire"
        elif "عادل" in rating:
            rating_class = "rating-ok"
        else:
            rating_class = "rating-bad"

        # Profit style
        profit_ask_class = "profit-positive" if profit_at_asking >= 0 else "profit-negative"
        profit_neg_class = "profit-positive" if profit_negotiated >= 0 else "profit-negative"

        # Negative profit warning
        warning_html = ""
        if profit_at_asking < 0:
            warning_html = f"""
            <div class="profit-warning">
                ⚠️ تحذير: لو اشتريت بالسعر المطلوب ({ask:,} ج.م) هتخسر {abs(profit_at_asking):,} ج.م!
                لازم تفاوض بقوة لـ {target_buy:,} أو تتجاوز الصفقة.
            </div>"""

        st.markdown(f"""
        <div class="card">
            <div class="card-title">🛒 نصيحة التداول (Flipping Advice)</div>
            <div class="rating-badge {rating_class}">{rating}</div>
            <div class="metrics-row">
                <div class="metric-box">
                    <div class="metric-label">السعر المطلوب</div>
                    <div class="metric-value" style="color:#ffb74d">{ask:,} ج.م</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">أقصى سعر شراء مستهدف</div>
                    <div class="metric-value green">{target_buy:,} ج.م</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">الربح الفوري (بدون فصال)</div>
                    <div class="{profit_ask_class}">{profit_at_asking:,} ج.م</div>
                </div>
                <div class="metric-box" style="border: 1px solid rgba(0, 230, 118, 0.4);">
                    <div class="metric-label">الربح بعد الفصال 🎯</div>
                    <div class="{profit_neg_class}">{profit_negotiated:,} ج.م</div>
                    <div style="font-size:0.75rem; color:#ffb74d; margin-top:5px">
                        مكسب الفصال: +{gain:,} ج.م
                    </div>
                </div>
            </div>
            {warning_html}
        </div>
        """, unsafe_allow_html=True)

elif analyze_btn and not account_text:
    st.warning("⚠️ أدخل تفاصيل الأكونت الأول عشان أقدر أحلله!")
