/* ==========================================================================
   PUBG MOBILE AI MARKET INTELLIGENCE - INTERACTIVE FRONTEND CONTROLLER
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initPresets();
    initInputActions();
    initEvaluator();
    initFilters();
    
    // Initial data fetch for market stats & mlops
    loadMarketTrends();
    loadMLOpsTelemetry();
});

/* --------------------------------------------------------------------------
   PRESETS DATA
   -------------------------------------------------------------------------- */
const PRESETS = {
    glacier: {
        text: `للبيع حساب ببجي موبايل فاخر
المستوى: 77
الأيدي: 5123456789
إمفور تلجي مكس (M416 Glacier MAX Level 7) 🔥
بدلة مومياء بيضاء كاملة 🧟
وش البنت الأصلي مع الشعر الأصلي 👩
بدلة ميثك لوبي خاصة 🏛️
سلاح يوزي الروماني لفل 4
سيارة ماكلارين ميثك الصفراء 🏎️
إطار كونكر الموسم 19 🏆
الربط: تويتر وبريد الكتروني متاحين والتسليم فوري مع الوسيط`,
        asking_price: 18500
    },
    xsuit: {
        text: `حساب ببجي لفل 80 أسطوري
بدلة اكس الفرعون مستوى 6 كاملة (X-Suit Pharoah Max) 👑
سيارة بورشه ميثك حمراء 🏎️
امفور جوكر لفل 5 (Joker M416) 🦊
إطار كونكر 3 مواسم 🏆
عدد الميثك: 85 قطعة ميثك
اسكارف النمر النادر 🐯
الربط: فيسبوك فقط وجميع الروابط النظيفة متاحة`,
        asking_price: 32000
    },
    economy: {
        text: `حساب ببجي اقتصادي ممتاز
المستوى: 68
امفور جوكر لفل 1
طقم الصابونة الزرقاء النادر 🧼
بدلة جيل جديدة
كار تلجي لفل 2
عدد الميثك: 22 ميثك
الربط: بريد الكتروني ورقم هاتف متاح التغيير`,
        asking_price: 4200
    }
};

/* --------------------------------------------------------------------------
   TAB SYSTEM
   -------------------------------------------------------------------------- */
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            const targetContent = document.getElementById(tabId);
            if (targetContent) {
                targetContent.classList.add('active');
            }

            // Refresh charts or telemetry on tab switch
            if (tabId === 'marketTab') loadMarketTrends();
            if (tabId === 'heatmapTab') loadHeatmap();
            if (tabId === 'mlopsTab') loadMLOpsTelemetry();
        });
    });
}

/* --------------------------------------------------------------------------
   PRESET & INPUT UTILITIES
   -------------------------------------------------------------------------- */
function initPresets() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.getAttribute('data-preset');
            if (PRESETS[key]) {
                const textarea = document.getElementById('listingText');
                const priceInput = document.getElementById('askingPriceInput');
                textarea.value = PRESETS[key].text;
                priceInput.value = PRESETS[key].asking_price;
                textarea.focus();
                
                // Highlight input wrapper
                textarea.parentElement.classList.add('highlight-preset');
                setTimeout(() => textarea.parentElement.classList.remove('highlight-preset'), 800);
            }
        });
    });
}

function initInputActions() {
    const pasteBtn = document.getElementById('pasteBtn');
    const clearBtn = document.getElementById('clearBtn');
    const textarea = document.getElementById('listingText');
    const priceInput = document.getElementById('askingPriceInput');
    const resultsContainer = document.getElementById('resultsContainer');

    if (pasteBtn) {
        pasteBtn.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text) textarea.value = text;
            } catch (err) {
                alert('الرجاء السماح بصلاحية الحافظة أو لصق النص يدوياً');
            }
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            textarea.value = '';
            priceInput.value = '';
            resultsContainer.classList.add('hidden');
            resultsContainer.innerHTML = '';
        });
    }
}

/* --------------------------------------------------------------------------
   ACCOUNT EVALUATOR CORE
   -------------------------------------------------------------------------- */
function initEvaluator() {
    const evaluateBtn = document.getElementById('evaluateBtn');
    if (evaluateBtn) {
        evaluateBtn.addEventListener('click', handleEvaluation);
    }
}

async function handleEvaluation() {
    const btn = document.getElementById('evaluateBtn');
    const btnText = btn.querySelector('.btn-text');
    const btnLoader = btn.querySelector('.btn-loader');
    const pipelineProgress = document.getElementById('pipelineProgress');
    const resultsContainer = document.getElementById('resultsContainer');

    const text = document.getElementById('listingText').value.trim();
    const askingPriceVal = document.getElementById('askingPriceInput').value.trim();
    const askingPrice = askingPriceVal ? parseFloat(askingPriceVal) : null;

    if (!text) {
        alert('الرجاء كتابة أو لصق تفاصيل إعلان الحساب أولاً');
        return;
    }

    // UI Loading state
    btn.disabled = true;
    btnText.classList.add('hidden');
    btnLoader.classList.remove('hidden');
    resultsContainer.classList.add('hidden');
    if (pipelineProgress) pipelineProgress.classList.remove('hidden');

    try {
        const response = await fetch('/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, asking_price: askingPrice })
        });

        if (!response.ok) throw new Error(`خطأ في الخادم (الكود ${response.status})`);
        
        const data = await response.json();
        renderEvaluationResults(data);
    } catch (error) {
        console.error("Evaluation error:", error);
        resultsContainer.innerHTML = `
            <div class="verdict-banner verdict-OVERPRICED">
                <div class="verdict-header"><i class="fa-solid fa-triangle-exclamation"></i> تعذر التقييم</div>
                <div class="verdict-desc">${error.message || 'حدث خطأ أثناء التواصل مع نموذج الذكاء الاصطناعي'}</div>
            </div>
        `;
        resultsContainer.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btnText.classList.remove('hidden');
        btnLoader.classList.add('hidden');
        if (pipelineProgress) pipelineProgress.classList.add('hidden');
    }
}

function renderEvaluationResults(data) {
    const container = document.getElementById('resultsContainer');
    const numFormatter = new Intl.NumberFormat('en-US');

    // 1. Verdict Banner Styling
    let verdictClass = 'verdict-FAIR_DEAL';
    let verdictIcon = '<i class="fa-solid fa-scale-balanced"></i>';
    let verdictTitle = 'تقييم متوافق وسعر عادل بالسوق';

    if (data.deal_verdict === 'GREAT_DEAL') {
        verdictClass = 'verdict-GREAT_DEAL';
        verdictIcon = '<i class="fa-solid fa-fire-flame-curved"></i>';
        verdictTitle = 'صفقة ممتازة (فرصة شراء ذكية)!';
    } else if (data.deal_verdict === 'OVERPRICED') {
        verdictClass = 'verdict-OVERPRICED';
        verdictIcon = '<i class="fa-solid fa-triangle-exclamation"></i>';
        verdictTitle = 'السعر المطلوب مبالغ فيه مقارنة بأسعار السوق';
    }

    // 2. High-Value Anchors Chips
    const anchors = data.highlighted_anchors || [];
    const anchorsHtml = anchors.length > 0
        ? anchors.map(a => `
            <div class="anchor-chip">
                <span>${a.icon} ${a.name}</span>
                <span class="anchor-tier-badge">Tier ${a.tier}</span>
            </div>
        `).join('')
        : '<span style="color:var(--text-muted); font-size:0.88rem;">لم يتم رصد ركائز فائقة الندرة (كالمومياء أو الإمفور التلجي الماكس)</span>';

    // 3. Extracted Inventory Grid
    const inv = data.inventory || {};
    const inventoryHtml = `
        <div class="inventory-grid">
            <div class="inventory-item-card">
                <div class="inventory-item-title"><i class="fa-solid fa-layer-group color-cyan"></i> مستوى الحساب</div>
                <div class="inventory-item-val color-cyan">Lvl ${inv.account_level}</div>
            </div>
            <div class="inventory-item-card">
                <div class="inventory-item-title"><i class="fa-solid fa-gem color-purple"></i> عدد الميثك</div>
                <div class="inventory-item-val color-purple">${inv.mythics_count}</div>
            </div>
            <div class="inventory-item-card">
                <div class="inventory-item-title"><i class="fa-solid fa-gun color-amber"></i> أسلحة التطوير (Lab)</div>
                <div class="inventory-item-val color-amber">${inv.guns_count}</div>
            </div>
            <div class="inventory-item-card">
                <div class="inventory-item-title"><i class="fa-solid fa-crown color-emerald"></i> بدل اكس (X-Suits)</div>
                <div class="inventory-item-val color-emerald">${inv.xsuits_count}</div>
            </div>
            <div class="inventory-item-card">
                <div class="inventory-item-title"><i class="fa-solid fa-car color-blue"></i> السيارات الميثك</div>
                <div class="inventory-item-val color-blue">${inv.cars_mythic} / ${inv.cars_total}</div>
            </div>
            <div class="inventory-item-card">
                <div class="inventory-item-title"><i class="fa-solid fa-chart-line color-rose"></i> معامل الندرة والـ Combo</div>
                <div class="inventory-item-val color-rose">x${inv.combo_multiplier}</div>
            </div>
        </div>
    `;

    // 4. Security Audit
    const sec = data.security || {};
    const trustScore = sec.trust_score || 70;
    const riskLevel = sec.risk_level || 'LOW';
    let trustColor = 'var(--emerald)';
    if (trustScore < 50) trustColor = 'var(--rose)';
    else if (trustScore < 75) trustColor = 'var(--amber)';

    const verifiedLinksHtml = (sec.verified_links || []).map(l => `<span class="tag-item" style="background:rgba(16,185,129,0.15); color:var(--emerald); border-color:rgba(16,185,129,0.3);">✓ ${l}</span>`).join(' ') || '<span style="color:var(--text-muted)">لا توجد روابط مؤكدة</span>';
    const assurancesHtml = (sec.assurances || []).map(a => `<li style="color:var(--emerald);"><i class="fa-solid fa-circle-check"></i> ${a}</li>`).join('');
    const warningsHtml = (sec.warnings || []).map(w => `<li style="color:var(--rose);"><i class="fa-solid fa-triangle-exclamation"></i> ${w}</li>`).join('') || '<li style="color:var(--text-muted);"><i class="fa-solid fa-check"></i> لا توجد علامات خطر حمراء عالية</li>';
    const precautionsHtml = (sec.precautions || []).map(p => `<li style="color:var(--amber);"><i class="fa-solid fa-lightbulb"></i> ${p}</li>`).join('');

    // 5. Detected Tags
    const items = data.detected_items || [];
    const tagsHtml = items.map(item => `<span class="tag-item">${item}</span>`).join('') || '<span style="color:var(--text-muted)">لا توجد وسوم نادرة مرصودة</span>';

    const askingPriceText = data.asking_price ? `${numFormatter.format(data.asking_price)} ج.م` : 'غير محدد';

    // Render HTML Output
    container.innerHTML = `
        <!-- Deal Verdict Banner -->
        <div class="verdict-banner ${verdictClass}">
            <div class="verdict-header">
                ${verdictIcon} ${verdictTitle}
            </div>
            <div class="verdict-desc">
                ${data.deal_explanation || ''}
            </div>
        </div>

        <!-- Key Valuation Metrics Grid -->
        <div class="eval-metrics-grid">
            <div class="metric-card">
                <div class="metric-label"><i class="fa-solid fa-hand-holding-dollar color-emerald"></i> التقييم العادل المستحق</div>
                <div class="metric-value-huge color-emerald">${numFormatter.format(data.fair_value_egp)} <span style="font-size:1rem; font-weight:normal;">ج.م</span></div>
                <div class="metric-subtext">السعر المطلوب من البائع: <b>${askingPriceText}</b></div>
            </div>

            <div class="metric-card">
                <div class="metric-label"><i class="fa-solid fa-chart-area color-cyan"></i> النطاق السعري المتوقع [P10 - P90]</div>
                <div class="metric-value-huge color-cyan" style="font-size:1.5rem; margin-top:0.4rem;">${data.price_range}</div>
                <div class="metric-subtext">تصنيف الحساب: <b>${data.segment || 'حساب عام'}</b></div>
            </div>

            <div class="metric-card">
                <div class="metric-label"><i class="fa-solid fa-shield-halved"></i> مؤشر أمان الحساب (Trust Score)</div>
                <div class="metric-value-huge" style="color:${trustColor};">${trustScore} <span style="font-size:1rem;">/ 100</span></div>
                <div class="metric-subtext">${sec.verdict_arabic || 'حساب مقبول الأمان'}</div>
            </div>
        </div>

        <!-- High-Value Anchors Spotlight -->
        <div class="anchors-card">
            <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
                <h3 style="font-size:1.05rem; color:var(--amber);"><i class="fa-solid fa-fire"></i> العناصر والركائز فائقة القيمة (High-Value Anchors)</h3>
            </div>
            <div class="anchors-grid">
                ${anchorsHtml}
            </div>
        </div>

        <!-- Extracted Inventory Specifications -->
        <div class="anchors-card">
            <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
                <h3 style="font-size:1.05rem; color:var(--cyan);"><i class="fa-solid fa-list-check"></i> مواصفات ومكونات الحساب المستخرجة</h3>
            </div>
            ${inventoryHtml}
        </div>

        <!-- Security & Link Audit -->
        <div class="security-audit-card">
            <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
                <h3 style="font-size:1.05rem;"><i class="fa-solid fa-user-shield color-emerald"></i> تقرير الأمان ونقاء الروابط (Security Audit)</h3>
                <span class="badge ${riskLevel === 'LOW' ? 'badge-emerald' : 'badge-rose'}">مستوى المخاطرة: ${riskLevel}</span>
            </div>

            <div style="margin-top:0.8rem;">
                <span style="font-size:0.85rem; color:var(--text-secondary);">الروابط المتاحة والمفحوصة:</span>
                <div style="margin-top:0.4rem;">${verifiedLinksHtml}</div>
            </div>

            <div class="audit-two-col">
                <div>
                    <span style="font-size:0.88rem; font-weight:700; color:var(--emerald);">مؤشرات الأمان والنقاء:</span>
                    <ul class="audit-list">${assurancesHtml}</ul>
                </div>
                <div>
                    <span style="font-size:0.88rem; font-weight:700; color:var(--rose);">ملاحظات ومخاطر مرصودة:</span>
                    <ul class="audit-list">${warningsHtml}</ul>
                </div>
            </div>

            <div style="margin-top:1rem; background:rgba(255,255,255,0.02); padding:0.8rem 1rem; border-radius:10px; border:1px solid rgba(255,255,255,0.05);">
                <span style="font-size:0.85rem; font-weight:700; color:var(--amber);">💡 نصائح وتوصيات للمشتري عند نقل الحساب:</span>
                <ul class="audit-list">${precautionsHtml}</ul>
            </div>
        </div>

        <!-- Detected Tags Cloud & Report Export -->
        <div class="tags-cloud-card">
            <div class="card-header" style="margin-bottom:0.5rem; padding-bottom:0.5rem;">
                <h3 style="font-size:1.05rem;"><i class="fa-solid fa-tags color-purple"></i> العناصر المحللة بالنص (${items.length} عنصر)</h3>
                <button id="copyReportBtn" class="icon-action-btn">
                    <i class="fa-regular fa-copy"></i> نسخ تقرير التقييم
                </button>
            </div>
            <div class="tags-cloud">
                ${tagsHtml}
            </div>
        </div>
    `;

    container.classList.remove('hidden');

    // Attach Copy Report event
    const copyBtn = document.getElementById('copyReportBtn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const reportText = `📊 تقرير تقييم حساب ببجي موبايل بالذكاء الاصطناعي:
💰 التقييم العادل: ${numFormatter.format(data.fair_value_egp)} ج.م
📈 النطاق السعري: ${data.price_range}
🛡️ مؤشر أمان الحساب: ${trustScore}/100
🔥 الركائز: ${anchors.map(a => a.name).join(' - ') || 'عادي'}
⚖️ نتيجة التقييم: ${data.deal_explanation || ''}`;
            navigator.clipboard.writeText(reportText);
            copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> تم النسخ!';
            setTimeout(() => copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> نسخ تقرير التقييم', 2000);
        });
    }
}

/* --------------------------------------------------------------------------
   TAB 2: MARKET ANALYTICS & CHART.JS
   -------------------------------------------------------------------------- */
let priceDistChart = null;
let m4DistChart = null;
let itemFreqChart = null;

async function loadMarketTrends() {
    const refreshBtn = document.getElementById('refreshMarketBtn');
    if (refreshBtn) refreshBtn.querySelector('i').classList.add('fa-spin');

    try {
        const response = await fetch('/market/trends');
        if (!response.ok) throw new Error("تعذر جلب بيانات السوق");

        const data = await response.json();
        renderMarketSummary(data.market_summary || {});
        renderPriceDistChart(data.price_distribution || {});
        renderM4DistChart(data.m4_distribution || []);
        renderItemFreqChart(data.item_frequency || []);
        renderPriceImpactTable(data.item_price_impact || []);
    } catch (err) {
        console.error("Market trends loading error:", err);
    } finally {
        if (refreshBtn) refreshBtn.querySelector('i').classList.remove('fa-spin');
    }
}

function renderMarketSummary(summary) {
    const numFormatter = new Intl.NumberFormat('en-US');

    document.getElementById('statTotalListings').innerText = numFormatter.format(summary.total_listings || 0);
    document.getElementById('statPricedRate').innerText = `${summary.price_detection_rate || 0}%`;
    document.getElementById('statPricedSub').innerText = `${numFormatter.format(summary.priced_listings || 0)} حساب مسعّر`;
    document.getElementById('statMedianPrice').innerText = `${numFormatter.format(summary.median_price_egp || 0)} ج.م`;
    document.getElementById('statChannelsCount').innerText = `${summary.channels_count || 0} متجر`;
}

function renderPriceDistChart(priceDist) {
    const ctx = document.getElementById('priceDistributionChart');
    if (!ctx) return;

    const segments = priceDist.segments || {};
    const labels = ['اقتصادي (<2k)', 'متوسط (2k-5k)', 'فوق متوسط (5k-10k)', 'ممتاز (10k-20k)', 'VIP (20k-50k)', 'Ultra (>50k)'];
    const dataVals = [
        segments.budget_0_2k || 0,
        segments.economy_2k_5k || 0,
        segments.mid_5k_10k || 0,
        segments.premium_10k_20k || 0,
        segments.whale_20k_50k || 0,
        segments.ultra_50k_plus || 0
    ];

    if (priceDistChart) priceDistChart.destroy();

    priceDistChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'عدد الحسابات في الشريحة',
                data: dataVals,
                backgroundColor: 'rgba(59, 130, 246, 0.65)',
                borderColor: '#3b82f6',
                borderWidth: 1.5,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { ticks: { color: '#94a3b8', font: { family: 'Cairo' } }, grid: { display: false } },
                y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

function renderM4DistChart(m4List) {
    const ctx = document.getElementById('m4DistributionChart');
    if (!ctx) return;

    const labels = m4List.map(m => m.type);
    const dataVals = m4List.map(m => m.count);

    if (m4DistChart) m4DistChart.destroy();

    m4DistChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: dataVals,
                backgroundColor: [
                    '#06b6d4', '#f59e0b', '#8b5cf6', '#10b981', '#f43f5e',
                    '#3b82f6', '#ec4899', '#6366f1', '#14b8a6', '#84cc16'
                ],
                borderWidth: 2,
                borderColor: '#08090e'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Cairo', size: 11 } } }
            }
        }
    });
}

function renderItemFreqChart(itemFreqList) {
    const ctx = document.getElementById('itemFrequencyChart');
    if (!ctx) return;

    const topItems = itemFreqList.slice(0, 10);
    const labels = topItems.map(i => i.item);
    const percentages = topItems.map(i => i.percentage);

    if (itemFreqChart) itemFreqChart.destroy();

    itemFreqChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'نسبة التكرار بالسوق (%)',
                data: percentages,
                backgroundColor: 'rgba(139, 92, 246, 0.65)',
                borderColor: '#8b5cf6',
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#94a3b8', font: { family: 'Cairo' } }, grid: { display: false } }
            }
        }
    });
}

function renderPriceImpactTable(impactList) {
    const container = document.getElementById('priceImpactTableContainer');
    if (!container) return;

    const numFormatter = new Intl.NumberFormat('en-US');
    const rowsHtml = impactList.slice(0, 8).map((item, idx) => `
        <tr>
            <td><b>#${idx + 1}</b></td>
            <td><strong>${item.item}</strong></td>
            <td>${numFormatter.format(item.accounts_with)} حساب</td>
            <td><span class="color-cyan">${numFormatter.format(item.median_price_with)} ج.م</span></td>
            <td><span style="color:var(--text-muted)">${numFormatter.format(item.median_price_without)} ج.م</span></td>
            <td><span class="color-emerald" style="font-weight:bold;">+${numFormatter.format(item.price_uplift_egp)} ج.م (+${item.price_uplift_pct}%)</span></td>
        </tr>
    `).join('');

    container.innerHTML = `
        <table class="custom-table">
            <thead>
                <tr>
                    <th>الترتيب</th>
                    <th>اسم العنصر النادر</th>
                    <th>الحسابات الحاملة له</th>
                    <th>وسيط السعر (بالعنصر)</th>
                    <th>وسيط السعر (بدونه)</th>
                    <th>مقدار الارتفاع المالي المضاف (Uplift)</th>
                </tr>
            </thead>
            <tbody>
                ${rowsHtml}
            </tbody>
        </table>
    `;
}

/* --------------------------------------------------------------------------
   TAB 3: RARITY & DEMAND HEATMAP
   -------------------------------------------------------------------------- */
let allHeatmapData = [];

function initFilters() {
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            const filterVal = pill.getAttribute('data-filter');
            renderHeatmapCards(filterVal);
        });
    });
}

async function loadHeatmap() {
    try {
        const response = await fetch('/market/heatmap');
        if (!response.ok) throw new Error("فشل جلب بيانات الخريطة");
        allHeatmapData = await response.json();
        renderHeatmapCards('ALL');
    } catch (err) {
        console.error("Heatmap fetch error:", err);
    }
}

function renderHeatmapCards(filter) {
    const container = document.getElementById('heatmapGrid');
    if (!container) return;

    const numFormatter = new Intl.NumberFormat('en-US');
    const filtered = filter === 'ALL'
        ? allHeatmapData
        : allHeatmapData.filter(h => h.signal === filter);

    container.innerHTML = filtered.map(h => {
        let barColor = 'var(--cyan)';
        if (h.signal === 'HOT') barColor = 'var(--rose)';
        if (h.signal === 'WARM') barColor = 'var(--amber)';

        return `
            <div class="heatmap-card">
                <div class="heatmap-card-header">
                    <span class="heatmap-item-title">${h.item}</span>
                    <span class="signal-badge signal-${h.signal}">${h.signal}</span>
                </div>

                <div class="score-bar-group">
                    <div class="score-bar-label">
                        <span>مؤشر الندرة (Rarity Score):</span>
                        <b>${h.rarity_score} / 100</b>
                    </div>
                    <div class="score-progress-track">
                        <div class="score-progress-fill" style="width:${h.rarity_score}%; background:${barColor};"></div>
                    </div>
                </div>

                <div class="score-bar-group">
                    <div class="score-bar-label">
                        <span>قوة الطلب (Demand Score):</span>
                        <b>${h.demand_score} / 100</b>
                    </div>
                    <div class="score-progress-track">
                        <div class="score-progress-fill" style="width:${h.demand_score}%; background:var(--purple);"></div>
                    </div>
                </div>

                <div style="font-size:0.82rem; color:var(--text-secondary); margin-top:0.8rem; display:flex; justify-content:space-between;">
                    <span>القيمة المضافة: <b class="color-emerald">+${numFormatter.format(h.price_uplift_egp)} ج.م</b></span>
                    <span>التكرار: <b>${h.frequency_pct}%</b></span>
                </div>
            </div>
        `;
    }).join('');
}

/* --------------------------------------------------------------------------
   TAB 4: MLOPS TELEMETRY & RETRAIN
   -------------------------------------------------------------------------- */
async function loadMLOpsTelemetry() {
    const container = document.getElementById('mlopsGrid');
    const retrainBtnHeader = document.getElementById('triggerRetrainBtnHeader');
    if (retrainBtnHeader) retrainBtnHeader.addEventListener('click', triggerRetrain);

    try {
        const response = await fetch('/mlops/status');
        if (!response.ok) throw new Error("تعذر جلب بيانات MLOps");

        const data = await response.json();
        const numFormatter = new Intl.NumberFormat('en-US');

        let driftBadgeClass = 'badge-emerald';
        if (data.drift_status.includes('MODERATE')) driftBadgeClass = 'badge-amber';
        if (data.drift_status.includes('ACTION')) driftBadgeClass = 'badge-rose';

        container.innerHTML = `
            <div class="telemetry-box">
                <div class="telemetry-title"><i class="fa-solid fa-database color-cyan"></i> إجمالي عينات التدريب</div>
                <div class="telemetry-val color-cyan">${numFormatter.format(data.dataset_total_rows || 0)}</div>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">حسابات جديدة منذ آخر تدريب: +${data.new_rows || 0}</div>
            </div>

            <div class="telemetry-box">
                <div class="telemetry-title"><i class="fa-solid fa-bullseye color-emerald"></i> متوسط الخطأ القائم (Model MAE)</div>
                <div class="telemetry-val color-emerald">${numFormatter.format(data.last_mae_egp || 0)} <span style="font-size:1rem;">ج.م</span></div>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">دقة التوقعات بالسوق</div>
            </div>

            <div class="telemetry-box">
                <div class="telemetry-title"><i class="fa-solid fa-wave-square color-purple"></i> مؤشر انحراف الخصائص (PSI Drift)</div>
                <div class="telemetry-val color-purple">${data.psi_score || 0}</div>
                <div style="margin-top:0.4rem;"><span class="badge ${driftBadgeClass}">${data.drift_status}</span></div>
            </div>

            <div class="telemetry-box">
                <div class="telemetry-title"><i class="fa-solid fa-clock-rotate-left color-amber"></i> تاريخ آخر إعادة تدريب</div>
                <div class="telemetry-val color-amber" style="font-size:1.2rem; margin-top:0.5rem;">${data.last_training_date || 'N/A'}</div>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">تحديث خوارزميات التجميع تلقائياً</div>
            </div>
        `;
    } catch (err) {
        console.error("MLOps error:", err);
    }
}

async function triggerRetrain() {
    const btn = document.getElementById('triggerRetrainBtnHeader');
    if (!btn) return;

    btn.disabled = true;
    const oldText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري التدريب الان...';

    try {
        const response = await fetch('/mlops/retrain', { method: 'POST' });
        if (!response.ok) throw new Error('فشل طلب إطلاق التدريب');
        alert('تم تدريب وتحديث نموذج الذكاء الاصطناعي بنجاح!');
        loadMLOpsTelemetry();
    } catch (err) {
        alert(`خطأ التدريب: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = oldText;
    }
}
