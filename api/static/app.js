/* ==========================================================================
   PUBG ORACLE — FRONTEND CONTROLLER
   Light product UI. All numbers come from the API; unknown values render as
   "—" (never null / fake zero). Icons: Lucide, refreshed after each render.
   ========================================================================== */

/* ── Small shared helpers ───────────────────────────────────────────────── */

const NF = new Intl.NumberFormat('en-US');

/** Lucide icon placeholder. `refreshIcons()` swaps it for inline SVG. */
function icon(name, cls = '') {
    return `<i data-lucide="${name}" class="ico ${cls}"></i>`;
}

/** Replaces every [data-lucide] placeholder inside `root` with an SVG. */
function refreshIcons(root = document) {
    if (!window.lucide || typeof window.lucide.createIcons !== 'function') {
        retryIconsLater();
        return;
    }
    const pascal = s => s.replace(/(^|-)([a-z0-9])/g, (_, __, c) => c.toUpperCase());
    const available = window.lucide.icons || {};
    root.querySelectorAll('[data-lucide]').forEach(el => {
        const name = el.getAttribute('data-lucide');
        if (!available[pascal(name)]) {
            el.setAttribute('data-lucide', 'circle');
        }
    });
    window.lucide.createIcons();
}

/* Lucide is deferred; a render can win the race. Retry briefly. */
let iconRetry = null;
function retryIconsLater() {
    if (iconRetry) return;
    let tries = 0;
    iconRetry = setInterval(() => {
        tries += 1;
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            clearInterval(iconRetry);
            iconRetry = null;
            refreshIcons(document);
        } else if (tries > 40) {
            clearInterval(iconRetry);
            iconRetry = null;
        }
    }, 125);
}

let toastTimer = null;
function toast(message, isError = false) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.classList.toggle('is-error', isError);
    el.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('is-visible'), 3200);
}

/** Formats a number, or returns "—" when the value was never measured. */
function fmt(v) {
    if (v === null || v === undefined || v === '' || v === 'N/A') return '—';
    const n = Number(v);
    return Number.isFinite(n) ? NF.format(n) : String(v);
}

function fmtMoney(v) {
    if (v === null || v === undefined || v === '' || !Number.isFinite(Number(v))) return '—';
    return `${NF.format(Math.round(Number(v)))} <small>ج.م</small>`;
}

function escapeHtml(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function shortDate(value) {
    if (!value) return '—';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '—';
    return new Intl.DateTimeFormat('ar-EG-u-nu-latn', {
        day: 'numeric', month: 'short', year: 'numeric',
    }).format(d);
}

/* ── Boot ───────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    refreshIcons();
    initTabs();
    initPresets();
    initInputActions();
    initEvaluator();
    initFilters();
    initSystemStatus();
    initHashRouting();

    // Shareable demo link: /?demo=glacier fills a sample and prices it.
    const demoKey = new URLSearchParams(window.location.search).get('demo');
    if (demoKey && PRESETS[demoKey]) {
        document.getElementById('listingText').value = PRESETS[demoKey].text;
        document.getElementById('askingPriceInput').value = PRESETS[demoKey].asking_price;
        handleEvaluation();
    }
});

/* ── System status strip ────────────────────────────────────────────────── */

async function initSystemStatus() {
    try {
        const health = await (await fetch('/health/data')).json();
        const listingsEl = document.getElementById('sysListings');
        const freshEl = document.getElementById('sysFreshness');
        const engineEl = document.getElementById('sysEngine');
        const dot = document.querySelector('.pulse-dot');
        const banner = document.getElementById('dataStaleBanner');
        const bannerText = document.getElementById('staleBannerText');

        if (listingsEl && health.listings_total != null) {
            listingsEl.textContent = NF.format(health.listings_total);
        }

        if (freshEl) {
            if (health.is_stale) {
                const hours = Number(health.hours_since_last);
                const days = Number.isFinite(hours) ? Math.max(1, Math.round(hours / 24)) : null;
                freshEl.textContent = days ? `البيانات متأخرة ${days} يوم` : 'البيانات متأخرة';
            } else {
                const hours = Math.max(0, Math.round(Number(health.hours_since_last) || 0));
                freshEl.textContent = hours < 1 ? 'محدّث الآن' : `محدّث قبل ${hours} ساعة`;
            }
        }

        if (health.is_stale) {
            dot?.classList.add('is-stale');
            if (engineEl) engineEl.lastChild.textContent = ' التقييم تقديري حتى وصول تحديث';
            if (banner && bannerText) {
                const last = shortDate(health.last_listing_at);
                const hours = Number(health.hours_since_last);
                const days = Number.isFinite(hours) ? Math.max(1, Math.round(hours / 24)) : null;
                bannerText.textContent = last === '—'
                    ? 'لا توجد إعلانات حديثة — الأرقام تقديرية حتى وصول تحديث من القنوات.'
                    : `آخر إعلان تم تحليله: ${last}${days ? ` (قبل ${days} يوم)` : ''} — الأرقام تقديرية حتى وصول تحديث.`;
                banner.classList.remove('hidden');
            }
        }
    } catch (err) {
        console.error('health error:', err);
    }

    try {
        const summary = await (await fetch('/market/summary')).json();
        const channelsEl = document.getElementById('sysChannels');
        if (channelsEl && summary.channels_count != null) {
            channelsEl.textContent = NF.format(summary.channels_count);
        }
    } catch (err) {
        console.error('summary error:', err);
    }
}

/* ── Presets ────────────────────────────────────────────────────────────── */

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
        asking_price: 18500,
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
        asking_price: 32000,
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
        asking_price: 4200,
    },
};

/* ── Tabs ───────────────────────────────────────────────────────────────── */

const TAB_LOADERS = {
    marketTab: () => loadMarketTrends(),
    itemIndexTab: () => loadItemIndex(),
    dealsTab: () => loadDealsTrust(),
    heatmapTab: () => loadHeatmap(),
    mlopsTab: () => loadMLOpsTelemetry(),
};

function activateTab(tabId, { updateHash = true } = {}) {
    const target = document.getElementById(tabId);
    if (!target) return;

    document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-tab') === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.toggle('active', c.id === tabId);
    });

    if (updateHash) {
        history.replaceState(null, '', `#${tabId}`);
    }

    if (TAB_LOADERS[tabId]) TAB_LOADERS[tabId]();
    refreshIcons();
}

function initTabs() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            activateTab(btn.getAttribute('data-tab'));
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
}

function initHashRouting() {
    const hash = (window.location.hash || '').replace('#', '');
    if (hash && document.getElementById(hash)?.classList.contains('tab-content')) {
        activateTab(hash, { updateHash: false });
    }
}

/* ── Input helpers ──────────────────────────────────────────────────────── */

function initPresets() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.getAttribute('data-preset');
            if (!PRESETS[key]) return;
            const textarea = document.getElementById('listingText');
            const priceInput = document.getElementById('askingPriceInput');
            textarea.value = PRESETS[key].text;
            priceInput.value = PRESETS[key].asking_price;
            textarea.focus();
            textarea.parentElement.classList.add('highlight-preset');
            setTimeout(() => textarea.parentElement.classList.remove('highlight-preset'), 700);
        });
    });
}

function initInputActions() {
    const pasteBtn = document.getElementById('pasteBtn');
    const clearBtn = document.getElementById('clearBtn');
    const textarea = document.getElementById('listingText');
    const priceInput = document.getElementById('askingPriceInput');
    const results = document.getElementById('resultsContainer');
    const placeholder = document.getElementById('evalPlaceholder');

    pasteBtn?.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) textarea.value = text;
        } catch {
            toast('السماح بصلاحية الحافظة مطلوب للصق التلقائي', true);
        }
    });

    clearBtn?.addEventListener('click', () => {
        textarea.value = '';
        priceInput.value = '';
        results.classList.add('hidden');
        results.innerHTML = '';
        placeholder?.classList.remove('hidden');
        textarea.focus();
    });

    // Ctrl/Cmd + Enter evaluates without reaching for the mouse.
    textarea?.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            handleEvaluation();
        }
    });
}

/* ── Evaluator ──────────────────────────────────────────────────────────── */

function initEvaluator() {
    document.getElementById('evaluateBtn')?.addEventListener('click', handleEvaluation);
}

async function handleEvaluation() {
    const btn = document.getElementById('evaluateBtn');
    const btnText = btn.querySelector('.btn-text');
    const btnLoader = btn.querySelector('.btn-loader');
    const progress = document.getElementById('pipelineProgress');
    const results = document.getElementById('resultsContainer');
    const placeholder = document.getElementById('evalPlaceholder');

    const text = document.getElementById('listingText').value.trim();
    const askingRaw = document.getElementById('askingPriceInput').value.trim();
    const askingPrice = askingRaw ? parseFloat(askingRaw) : null;

    if (!text) {
        toast('الصق نص الإعلان أولاً', true);
        document.getElementById('listingText').focus();
        return;
    }

    btn.disabled = true;
    btnText.classList.add('hidden');
    btnLoader.classList.remove('hidden');
    results.classList.add('hidden');
    placeholder?.classList.add('hidden');
    progress?.classList.remove('hidden');

    try {
        const response = await fetch('/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, asking_price: askingPrice }),
        });
        if (!response.ok) throw new Error(`تعذر إكمال التقييم (الكود ${response.status})`);
        renderEvaluationResults(await response.json());
    } catch (error) {
        console.error('Evaluation error:', error);
        results.innerHTML = `
            <div class="verdict verdict--over">
                <span class="verdict-icon">${icon('triangle-alert')}</span>
                <div class="verdict-body">
                    <div class="verdict-title">تعذر التقييم</div>
                    <p class="verdict-desc">${escapeHtml(error.message || 'حدث خطأ أثناء التواصل مع الخادم')}</p>
                </div>
            </div>`;
        results.classList.remove('hidden');
        refreshIcons(results);
    } finally {
        btn.disabled = false;
        btnText.classList.remove('hidden');
        btnLoader.classList.add('hidden');
        progress?.classList.add('hidden');
    }
}

function parsePriceRange(raw) {
    const match = String(raw || '').match(/([\d.,]+)\s*[-–]\s*([\d.,]+)/);
    if (!match) return null;
    const a = parseFloat(match[1].replace(/,/g, ''));
    const b = parseFloat(match[2].replace(/,/g, ''));
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    return a <= b ? [a, b] : [b, a];
}

function renderEvaluationResults(data) {
    const container = document.getElementById('resultsContainer');
    const fair = Number(data.fair_value_egp);
    const ask = data.asking_price != null ? Number(data.asking_price) : null;
    const range = parsePriceRange(data.price_range);
    const inv = data.inventory || {};
    const sec = data.security || {};
    const anchors = data.highlighted_anchors || [];
    const items = data.detected_items || [];

    /* Verdict */
    const verdicts = {
        GREAT_DEAL: { cls: 'great', ic: 'flame', title: 'فرصة شراء', fallback: 'السعر المطلوب أقل من القيمة العادلة.' },
        FAIR_DEAL: { cls: 'fair', ic: 'scale', title: 'سعر عادل', fallback: 'السعر المطلوب متوافق مع السوق.' },
        OVERPRICED: { cls: 'over', ic: 'triangle-alert', title: 'السعر مبالغ فيه', fallback: 'السعر المطلوب أعلى من القيمة العادلة.' },
        FAIR_EVALUATION: { cls: 'fair', ic: 'badge-check', title: 'تقييم جاهز', fallback: 'تم التقييم بناءً على عناصر الحساب.' },
    };
    const v = verdicts[data.deal_verdict] || verdicts.FAIR_EVALUATION;

    /* Asking vs fair delta */
    let deltaHtml = '';
    if (ask != null && Number.isFinite(fair) && fair > 0) {
        const pct = ((ask - fair) / fair) * 100;
        const kind = pct > 2 ? 'bad' : pct < -2 ? 'good' : 'neutral';
        const label = kind === 'bad' ? 'أعلى من العادل' : kind === 'good' ? 'أقل من العادل' : 'مطابق للعادل';
        deltaHtml = `<span class="delta delta--${kind}" dir="ltr">${pct > 0 ? '+' : ''}${pct.toFixed(1)}%</span>
                     <span class="muted-note">${label}</span>`;
    }

    /* Range bar */
    let rangeHtml = '<p class="muted-note">النطاق غير متاح لهذا الحساب.</p>';
    if (range) {
        const [lo, hi] = range;
        const span = Math.max(1, hi - lo);
        const pos = value => Math.max(0, Math.min(100, ((value - lo) / span) * 100));
        const fairPos = pos(fair);
        const askPos = ask != null ? pos(ask) : null;
        const askOutside = ask != null && (ask < lo || ask > hi);
        rangeHtml = `
            <div class="range">
                <div class="range-track">
                    <div class="range-fill"></div>
                    <span class="range-marker is-fair" style="left:${fairPos}%" title="السعر العادل"></span>
                    ${askPos != null ? `<span class="range-marker is-ask" style="left:${askPos}%" title="سعر البائع"></span>` : ''}
                </div>
                <div class="range-labels">
                    <span>${NF.format(Math.round(lo))}</span>
                    <span>${NF.format(Math.round(hi))}</span>
                </div>
                <div class="range-legend">
                    <span><i class="legend-dot is-fair"></i> العادل</span>
                    ${ask != null ? '<span><i class="legend-dot is-ask"></i> المطلوب</span>' : ''}
                    ${askOutside ? '<span class="color-amber">سعر البائع خارج النطاق</span>' : ''}
                </div>
            </div>`;
    }

    /* Trust ring */
    const score = Math.max(0, Math.min(100, Number(sec.trust_score ?? 0)));
    const trustClass = score < 50 ? 'is-bad' : score < 75 ? 'is-warn' : '';
    const circumference = 2 * Math.PI * 32;
    const ringOffset = circumference * (1 - score / 100);
    const riskLabel = sec.risk_level === 'LOW' ? 'مخاطرة منخفضة'
        : sec.risk_level === 'MEDIUM' ? 'مخاطرة متوسطة' : 'مخاطرة مرتفعة';

    /* Inventory */
    const spec = (label, ic, value, ltr = false) => {
        const unknown = value === null || value === undefined || value === '' || value === 'N/A';
        return `<div class="spec">
            <span class="spec-k">${icon(ic)} ${label}</span>
            <span class="spec-v ${unknown ? 'is-unknown' : ''}" ${ltr ? 'dir="ltr"' : ''}>${unknown ? '—' : escapeHtml(value)}</span>
        </div>`;
    };
    const inventoryHtml = `
        <div class="spec-grid">
            ${spec('مستوى الحساب', 'layers', inv.account_level)}
            ${spec('عدد الميثك', 'gem', inv.mythics_count)}
            ${spec('أسلحة تطوير', 'crosshair', inv.guns_count)}
            ${spec('بدل اكس', 'crown', inv.xsuits_count)}
            ${spec('سيارات ميثك/إجمالي', 'car', `${fmt(inv.cars_mythic)} / ${fmt(inv.cars_total)}`, true)}
            ${spec('إطارات كونكر', 'trophy', inv.conqueror_frames)}
            ${spec('برستيج', 'star', inv.prestige_score)}
            ${spec('معامل الندرة', 'trending-up', inv.combo_multiplier != null ? `×${fmt(inv.combo_multiplier)}` : null, true)}
        </div>`;

    /* Anchors */
    const anchorsHtml = anchors.length
        ? anchors.map(a => `<span class="anchor">${escapeHtml(a.name)}<span class="anchor-tier" dir="ltr">${escapeHtml(a.tier)}</span></span>`).join('')
        : '<span class="muted-note">لم يتم رصد ركائز فائقة الندرة (مثل الإمفور التلجي الماكس أو المومياء).</span>';

    /* Security lists */
    const linksHtml = (sec.verified_links || []).length
        ? sec.verified_links.map(l => `<span class="tag is-link">${icon('check')} ${escapeHtml(l)}</span>`).join('')
        : '<span class="muted-note">لا توجد روابط مؤكدة</span>';

    const assurancesHtml = (sec.assurances || []).length
        ? sec.assurances.map(a => `<li class="is-green">${icon('circle-check')}<span>${escapeHtml(a)}</span></li>`).join('')
        : '<li class="is-green">' + icon('circle-check') + '<span>لا توجد مشاكل أمان مرصودة</span></li>';

    const warningsHtml = (sec.warnings || []).length
        ? sec.warnings.map(w => `<li class="is-red">${icon('triangle-alert')}<span>${escapeHtml(w)}</span></li>`).join('')
        : `<li>${icon('check')}<span>لا توجد علامات خطر حمراء</span></li>`;

    const precautionsHtml = (sec.precautions || []).map(p => `<li class="is-gold">${icon('lightbulb')}<span>${escapeHtml(p)}</span></li>`).join('');

    /* Model breakdown */
    const mb = data.models_breakdown || {};
    const modelCell = (label, value) => `
        <div class="model">
            <span class="model-k">${label}</span>
            <span class="model-v">${value != null ? NF.format(Math.round(Number(value))) : '—'}</span>
        </div>`;
    const modelsHtml = `
        <div class="models">
            ${modelCell('XGBoost', mb.xgboost_estimate)}
            ${modelCell('CatBoost', mb.catboost_estimate)}
            ${modelCell('LightGBM', mb.lightgbm_estimate)}
        </div>
        ${mb.note ? `<p class="muted-note" style="margin-top:8px">${escapeHtml(mb.note)}</p>` : ''}`;

    const confidence = data.confidence || {};
    const confScore = confidence.score ? String(confidence.score) : null;

    const tagsHtml = items.length
        ? items.map(item => `<span class="tag">${escapeHtml(item)}</span>`).join('')
        : '<span class="muted-note">لا توجد وسوم نادرة مرصودة</span>';

    container.innerHTML = `
        <div class="verdict verdict--${v.cls}">
            <span class="verdict-icon">${icon(v.ic)}</span>
            <div class="verdict-body">
                <div class="verdict-title">${v.title}</div>
                <p class="verdict-desc">${escapeHtml(data.deal_explanation || v.fallback)}</p>
            </div>
        </div>

        <div class="valuation">
            <div>
                <span class="k">السعر العادل المستحق</span>
                <div class="value">${fmtMoney(fair)}</div>
                <div class="value-note">
                    <span>السعر المطلوب: <b>${ask != null ? fmtMoney(ask) : 'غير محدد'}</b></span>
                    ${deltaHtml}
                </div>
                ${confScore ? `<div class="value-note"><span class="badge badge-blue">${icon('gauge')} ثقة التقييم ${escapeHtml(confScore)} — ${escapeHtml(confidence.label || '')}</span></div>` : ''}
            </div>
            <div class="valuation-side">
                <span class="k">النطاق المتوقع P10 – P90</span>
                ${rangeHtml}
                <div style="margin-top:14px">
                    <span class="k">تصنيف الحساب</span>
                    <span class="muted-note" dir="auto">${escapeHtml(data.segment || 'حساب عام')}</span>
                </div>
            </div>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-head"><h3>${icon('shield-check')} أمان الحساب</h3>
                    <span class="badge ${score >= 75 ? 'badge-green' : score >= 50 ? 'badge-gold' : 'badge-red'}">${riskLabel}</span>
                </div>
                <div class="trust">
                    <div class="trust-ring ${trustClass}">
                        <svg width="76" height="76" viewBox="0 0 76 76" aria-hidden="true">
                            <circle class="ring-bg" cx="38" cy="38" r="32"></circle>
                            <circle class="ring-fg" cx="38" cy="38" r="32"
                                stroke-dasharray="${circumference.toFixed(1)}"
                                stroke-dashoffset="${ringOffset.toFixed(1)}"></circle>
                        </svg>
                        <span class="trust-score">${score}</span>
                    </div>
                    <div class="trust-copy">
                        <div class="trust-title">${escapeHtml(sec.verdict_arabic || 'حساب مقبول الأمان')}</div>
                        <div class="trust-sub">مؤشر الثقة من 100</div>
                    </div>
                </div>
                <div class="tag-list" style="margin-top:12px">${linksHtml}</div>
            </div>

            <div class="card">
                <div class="card-head"><h3>${icon('flame')} العناصر فائقة القيمة</h3>
                    <span class="badge badge-gold">${anchors.length} عنصر</span>
                </div>
                <div class="anchor-list">${anchorsHtml}</div>
            </div>

            <div class="card">
                <div class="card-head"><h3>${icon('layers')} مكونات الحساب</h3></div>
                ${inventoryHtml}
            </div>
        </div>

        <div class="card card-wide">
            <div class="card-head"><h3>${icon('clipboard-check')} تقرير الأمان والروابط</h3></div>
            <div class="audit-grid">
                <div class="audit-col">
                    <div class="audit-title is-green">${icon('circle-check')} مؤشرات الأمان</div>
                    <ul class="audit-list">${assurancesHtml}</ul>
                </div>
                <div class="audit-col">
                    <div class="audit-title is-red">${icon('triangle-alert')} ملاحظات ومخاطر</div>
                    <ul class="audit-list">${warningsHtml}</ul>
                </div>
                <div class="audit-col">
                    <div class="audit-title is-gold">${icon('lightbulb')} توصيات قبل النقل</div>
                    <ul class="audit-list">${precautionsHtml || '<li><span>—</span></li>'}</ul>
                </div>
            </div>
        </div>

        <div class="cards cards-split">
            <div class="card">
                <div class="card-head"><h3>${icon('cpu')} تفصيل النماذج</h3></div>
                ${modelsHtml}
            </div>
            <div class="card">
                <div class="card-head">
                    <h3>${icon('tags')} العناصر المحللة (${items.length})</h3>
                    <button id="copyReportBtn" type="button" class="btn btn-ghost btn-xs">${icon('copy')} نسخ التقرير</button>
                </div>
                <div class="tag-list">${tagsHtml}</div>
            </div>
        </div>
    `;

    container.classList.remove('hidden');
    refreshIcons(container);

    document.getElementById('copyReportBtn')?.addEventListener('click', async () => {
        const lines = [
            'تقرير تقييم حساب ببجي موبايل — PUBG Oracle',
            `السعر العادل: ${NF.format(Math.round(fair))} ج.م`,
            `النطاق المتوقع: ${data.price_range || '—'}`,
            `السعر المطلوب: ${ask != null ? NF.format(Math.round(ask)) + ' ج.م' : 'غير محدد'}`,
            `مؤشر الأمان: ${score}/100 (${sec.verdict_arabic || ''})`,
            `الركائز: ${anchors.map(a => a.name).join(' — ') || 'لا يوجد'}`,
            `النتيجة: ${data.deal_explanation || ''}`,
        ];
        try {
            await navigator.clipboard.writeText(lines.join('\n'));
            toast('تم نسخ التقرير');
        } catch {
            toast('تعذر النسخ — انسخ النص يدويًا', true);
        }
    });

    // Mobile: bring the answer into view instead of leaving it below the fold.
    if (window.matchMedia('(max-width: 720px)').matches) {
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/* ── Market analytics ───────────────────────────────────────────────────── */

let priceDistChart = null;
let m4DistChart = null;
let itemFreqChart = null;

const CHART = {
    ink: '#101828',
    muted: '#667085',
    grid: '#eef0f3',
    brand: '#0d7a63',
    brandSoft: 'rgba(13, 122, 99, 0.14)',
    gold: '#c47f0a',
    blue: '#4a7bd0',
    palette: ['#0d7a63', '#4a7bd0', '#c47f0a', '#7a5af8', '#e26d5c', '#4ea8a0', '#98a2b3', '#b7791f', '#5b8def', '#8f6bd8'],
};

function chartBase() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: CHART.muted, font: { family: "'IBM Plex Sans Arabic', sans-serif", size: 11 } }, grid: { display: false } },
            y: { beginAtZero: true, ticks: { color: CHART.muted, font: { family: "'JetBrains Mono', monospace", size: 10 } }, grid: { color: CHART.grid } },
        },
    };
}

async function loadMarketTrends() {
    const btn = document.getElementById('refreshMarketBtn');
    btn?.classList.add('is-spinning');
    try {
        const response = await fetch('/market/trends');
        if (!response.ok) throw new Error('تعذر جلب بيانات السوق');
        const data = await response.json();
        renderMarketSummary(data.market_summary || {});
        renderPriceDistChart(data.price_distribution || {});
        renderM4DistChart(data.m4_distribution || []);
        renderItemFreqChart(data.item_frequency || []);
        renderPriceImpactTable(data.item_price_impact || []);
    } catch (err) {
        console.error('Market trends loading error:', err);
        toast('تعذر تحميل مؤشرات السوق', true);
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

function renderMarketSummary(summary) {
    document.getElementById('statTotalListings').textContent = NF.format(summary.total_listings || 0);
    document.getElementById('statPricedRate').textContent = `${summary.price_detection_rate || 0}%`;
    document.getElementById('statPricedSub').textContent = `${NF.format(summary.priced_listings || 0)} حساب مسعّر`;
    document.getElementById('statMedianPrice').textContent = `${NF.format(summary.median_price_egp || 0)} ج.م`;
    document.getElementById('statChannelsCount').textContent = `${summary.channels_count || 0} قناة`;
}

function renderPriceDistChart(priceDist) {
    const ctx = document.getElementById('priceDistributionChart');
    if (!ctx || typeof Chart === 'undefined') return;

    const s = priceDist.segments || {};
    const labels = ['<2k', '2k–5k', '5k–10k', '10k–20k', '20k–50k', '>50k'];
    const values = [s.budget_0_2k, s.economy_2k_5k, s.mid_5k_10k, s.premium_10k_20k, s.whale_20k_50k, s.ultra_50k_plus]
        .map(v => v || 0);

    priceDistChart?.destroy();
    priceDistChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: CHART.brandSoft,
                borderColor: CHART.brand,
                borderWidth: 1.5,
                borderRadius: 6,
                maxBarThickness: 46,
            }],
        },
        options: chartBase(),
    });
}

function renderM4DistChart(m4List) {
    const ctx = document.getElementById('m4DistributionChart');
    if (!ctx || typeof Chart === 'undefined') return;

    m4DistChart?.destroy();
    m4DistChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: m4List.map(m => m.type),
            datasets: [{
                data: m4List.map(m => m.count),
                backgroundColor: CHART.palette,
                borderWidth: 2,
                borderColor: '#ffffff',
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '58%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: CHART.muted,
                        boxWidth: 10,
                        boxHeight: 10,
                        padding: 12,
                        font: { family: "'IBM Plex Sans Arabic', sans-serif", size: 11 },
                    },
                },
            },
        },
    });
}

function renderItemFreqChart(itemFreqList) {
    const ctx = document.getElementById('itemFrequencyChart');
    if (!ctx || typeof Chart === 'undefined') return;

    const top = itemFreqList.slice(0, 10);
    itemFreqChart?.destroy();
    itemFreqChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top.map(i => i.item),
            datasets: [{
                data: top.map(i => i.percentage),
                backgroundColor: 'rgba(74, 123, 208, 0.14)',
                borderColor: CHART.blue,
                borderWidth: 1.5,
                borderRadius: 6,
                maxBarThickness: 18,
            }],
        },
        options: {
            ...chartBase(),
            indexAxis: 'y',
            scales: {
                x: { beginAtZero: true, ticks: { color: CHART.muted, callback: v => `${v}%` }, grid: { color: CHART.grid } },
                y: { ticks: { color: CHART.muted, font: { family: "'IBM Plex Sans Arabic', sans-serif", size: 11 } }, grid: { display: false } },
            },
        },
    });
}

function renderPriceImpactTable(impactList) {
    const container = document.getElementById('priceImpactTableContainer');
    if (!container) return;

    if (!impactList.length) {
        container.innerHTML = '<p class="muted-note" style="padding:16px">لا توجد بيانات كافية بعد.</p>';
        return;
    }

    const rows = impactList.slice(0, 8).map((item, idx) => `
        <tr>
            <td><b>${idx + 1}</b></td>
            <td><strong>${escapeHtml(item.item)}</strong></td>
            <td>${NF.format(item.accounts_with)} حساب</td>
            <td>${NF.format(item.median_price_with)} ج.م</td>
            <td class="color-muted">${NF.format(item.median_price_without)} ج.م</td>
            <td><b class="color-green">+${NF.format(item.price_uplift_egp)} ج.م</b> <span class="color-muted">(+${item.price_uplift_pct}%)</span></td>
        </tr>`).join('');

    container.innerHTML = `
        <table class="data-table">
            <thead><tr>
                <th>#</th><th>العنصر</th><th>حسابات تحمله</th>
                <th>وسيط السعر معه</th><th>بدونه</th><th>القيمة المضافة</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

/* ── Rarity & demand ────────────────────────────────────────────────────── */

let allHeatmapData = [];

function initFilters() {
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            renderHeatmapCards(pill.getAttribute('data-filter'));
        });
    });
}

async function loadHeatmap() {
    try {
        const response = await fetch('/market/heatmap');
        if (!response.ok) throw new Error('فشل جلب بيانات الخريطة');
        allHeatmapData = await response.json();
        renderHeatmapCards('ALL');
    } catch (err) {
        console.error('Heatmap fetch error:', err);
        toast('تعذر تحميل مصفوفة الطلب', true);
    }
}

function renderHeatmapCards(filter) {
    const container = document.getElementById('heatmapGrid');
    if (!container) return;

    const filtered = filter === 'ALL' ? allHeatmapData : allHeatmapData.filter(h => h.signal === filter);
    if (!filtered.length) {
        container.innerHTML = '<p class="muted-note">لا توجد عناصر في هذه الفئة.</p>';
        return;
    }

    container.innerHTML = filtered.map(h => {
        const rarityColor = h.signal === 'HOT' ? 'is-red' : h.signal === 'WARM' ? 'is-gold' : 'is-blue';
        return `
            <div class="heat-card">
                <div class="heat-head">
                    <span class="heat-title">${escapeHtml(h.item)}</span>
                    <span class="signal signal-${escapeHtml(h.signal)}">${escapeHtml(h.signal)}</span>
                </div>
                <div class="bar-group">
                    <div class="bar-label"><span>الندرة</span><b>${h.rarity_score}/100</b></div>
                    <div class="bar-track"><div class="bar-fill ${rarityColor}" style="width:${h.rarity_score}%"></div></div>
                </div>
                <div class="bar-group">
                    <div class="bar-label"><span>الطلب</span><b>${h.demand_score}/100</b></div>
                    <div class="bar-track"><div class="bar-fill" style="width:${h.demand_score}%"></div></div>
                </div>
                <div class="heat-foot">
                    <span>القيمة المضافة: <b class="color-green">+${NF.format(h.price_uplift_egp)}</b></span>
                    <span>التكرار: <b>${h.frequency_pct}%</b></span>
                </div>
            </div>`;
    }).join('');
}

/* ── System / MLOps ─────────────────────────────────────────────────────── */

let retrainBound = false;

async function loadMLOpsTelemetry() {
    const container = document.getElementById('mlopsGrid');
    const retrainBtn = document.getElementById('triggerRetrainBtnHeader');
    if (retrainBtn && !retrainBound) {
        retrainBtn.addEventListener('click', triggerRetrain);
        retrainBound = true;
    }

    try {
        const response = await fetch('/mlops/status');
        if (!response.ok) throw new Error('تعذر جلب بيانات النظام');
        const data = await response.json();

        let driftBadge = 'badge-green';
        if (String(data.drift_status || '').includes('MODERATE')) driftBadge = 'badge-gold';
        if (String(data.drift_status || '').includes('ACTION')) driftBadge = 'badge-red';

        container.innerHTML = `
            <div class="stat-card">
                <span class="stat-k">عينات التدريب</span>
                <span class="stat-v">${NF.format(data.dataset_total_rows || 0)}</span>
                <span class="stat-s">+${data.new_rows || 0} حساب منذ آخر تدريب</span>
            </div>
            <div class="stat-card">
                <span class="stat-k">متوسط الخطأ (MAE)</span>
                <span class="stat-v">${NF.format(data.last_mae_egp || 0)}</span>
                <span class="stat-s">ج.م — دقة التوقعات</span>
            </div>
            <div class="stat-card">
                <span class="stat-k">انحراف الخصائص (PSI)</span>
                <span class="stat-v">${data.psi_score ?? '—'}</span>
                <span class="stat-s"><span class="badge ${driftBadge}">${escapeHtml(data.drift_status || 'غير معروف')}</span></span>
            </div>
            <div class="stat-card">
                <span class="stat-k">آخر إعادة تدريب</span>
                <span class="stat-v" style="font-size:17px">${escapeHtml(data.last_training_date || '—')}</span>
                <span class="stat-s">تحديث تلقائي للخوارزميات</span>
            </div>`;
    } catch (err) {
        console.error('MLOps error:', err);
        toast('تعذر تحميل حالة النظام', true);
    }
}

async function triggerRetrain() {
    const btn = document.getElementById('triggerRetrainBtnHeader');
    if (!btn) return;
    btn.disabled = true;
    btn.classList.add('is-spinning');
    try {
        const response = await fetch('/mlops/retrain', { method: 'POST' });
        if (!response.ok) throw new Error('فشل طلب إعادة التدريب');
        toast('تم إطلاق إعادة التدريب');
        loadMLOpsTelemetry();
    } catch (err) {
        toast(`خطأ: ${err.message}`, true);
    } finally {
        btn.disabled = false;
        btn.classList.remove('is-spinning');
    }
}

/* ── Item price index ───────────────────────────────────────────────────── */

let itemIndexData = null;
let itemIndexChartInstance = null;

async function loadItemIndex() {
    const select = document.getElementById('itemIndexSelect');
    if (!select) return;

    const refreshBtn = document.getElementById('refreshItemIndexBtn');
    if (refreshBtn && !refreshBtn.dataset.bound) {
        refreshBtn.addEventListener('click', loadItemIndex);
        refreshBtn.dataset.bound = '1';
    }
    if (!select.dataset.bound) {
        select.addEventListener('change', renderItemIndexChart);
        select.dataset.bound = '1';
    }

    try {
        const res = await fetch('/market/item-index');
        itemIndexData = (await res.json()).items;
    } catch (err) {
        console.error('item index error:', err);
        toast('تعذر تحميل بورصة العناصر', true);
        return;
    }

    const ids = Object.keys(itemIndexData).sort((a, b) =>
        Math.abs(itemIndexData[b].current_uplift_egp) - Math.abs(itemIndexData[a].current_uplift_egp));

    const counts = { rising: 0, falling: 0, stable: 0 };
    ids.forEach(id => { if (counts[itemIndexData[id].trend] != null) counts[itemIndexData[id].trend]++; });

    document.getElementById('itemIndexTrendCards').innerHTML = `
        <div class="stat-card">
            <span class="stat-k">عناصر صاعدة</span>
            <span class="stat-v color-green">${counts.rising}</span>
            <span class="stat-s">الطلب يزيد عليها</span>
        </div>
        <div class="stat-card">
            <span class="stat-k">مستقرة</span>
            <span class="stat-v">${counts.stable}</span>
            <span class="stat-s">سعر ثابت نسبيًا</span>
        </div>
        <div class="stat-card">
            <span class="stat-k">عناصر هابطة</span>
            <span class="stat-v color-red">${counts.falling}</span>
            <span class="stat-s">فرصة شراء محتملة</span>
        </div>`;

    select.innerHTML = ids.map(id => {
        const c = itemIndexData[id];
        const sign = c.current_uplift_egp >= 0 ? '+' : '';
        return `<option value="${escapeHtml(id)}">${escapeHtml(id)} (${sign}${NF.format(c.current_uplift_egp)} EGP)</option>`;
    }).join('');
    select.dataset.loaded = '1';

    const rows = ids.slice(0, 15).map(id => {
        const c = itemIndexData[id];
        const trend = c.trend === 'rising'
            ? `<span class="color-green">${icon('trending-up')} صاعد</span>`
            : c.trend === 'falling'
                ? `<span class="color-red">${icon('trending-down')} هابط</span>`
                : `<span class="color-muted">${icon('minus')} مستقر</span>`;
        return `<tr>
            <td><b>${escapeHtml(id)}</b></td>
            <td class="num">${c.current_uplift_egp >= 0 ? '+' : ''}${NF.format(c.current_uplift_egp)}</td>
            <td>${trend}</td>
            <td>${c.median_price_with_item ? NF.format(c.median_price_with_item) : '—'}</td>
            <td>${c.share_of_listings_pct}%</td>
            <td>${NF.format(c.total_observations)}</td>
        </tr>`;
    }).join('');

    document.getElementById('itemIndexTableContainer').innerHTML = `
        <table class="data-table">
            <thead><tr>
                <th>العنصر</th><th>القيمة (EGP)</th><th>الاتجاه</th>
                <th>وسيط سعر حساب به</th><th>الانتشار</th><th>مشاهدات</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>`;

    renderItemIndexChart();
}

function renderItemIndexChart() {
    if (!itemIndexData) return;
    const id = document.getElementById('itemIndexSelect').value;
    const card = itemIndexData[id];
    if (!card) return;

    document.getElementById('itemIndexMeta').innerHTML =
        `آخر تحديث: <b>${escapeHtml(card.last_month)}</b> · مشاهدات: ${NF.format(card.total_observations)} · وسيط السعر معه: <b>${NF.format(card.median_price_with_item || 0)}</b> ج.م`;

    const ctx = document.getElementById('itemIndexChart');
    if (!ctx || typeof Chart === 'undefined') return;

    itemIndexChartInstance?.destroy();
    itemIndexChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: card.series.map(p => p.month),
            datasets: [{
                label: `${id} (EGP)`,
                data: card.series.map(p => p.uplift_egp),
                borderColor: CHART.brand,
                backgroundColor: CHART.brandSoft,
                fill: true,
                tension: 0.35,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: CHART.brand,
            }],
        },
        options: {
            ...chartBase(),
            scales: {
                x: { ticks: { color: CHART.muted }, grid: { display: false } },
                y: { ticks: { color: CHART.muted, callback: v => NF.format(v) }, grid: { color: CHART.grid } },
            },
        },
    });
}

/* ── Live deals + trust ─────────────────────────────────────────────────── */

let dealsSocket = null;

function setLiveFeedStatus(connected) {
    const el = document.getElementById('liveFeedStatus');
    if (!el) return;
    el.className = `badge ${connected ? 'badge-green' : 'badge-muted'}`;
    el.innerHTML = connected
        ? `${icon('wifi')} متصل — بث حي`
        : `${icon('wifi-off')} غير متصل`;
    refreshIcons(el);
}

function appendDealCard(deal) {
    const feed = document.getElementById('liveDealsFeed');
    if (!feed) return;
    feed.querySelector('.feed-empty')?.remove();

    const asked = deal.asked_price != null ? `${NF.format(deal.asked_price)} ج.م` : 'بدون سعر';
    const profit = deal.profit != null ? NF.format(deal.profit) : '—';
    const rating = (deal.deal_rating || '').includes('اشترِ') ? icon('flame')
        : (deal.deal_rating || '').includes('غالي') ? icon('snowflake') : icon('thumbs-up');

    const div = document.createElement('div');
    div.className = 'deal-card';
    div.innerHTML = `
        <div class="deal-head">
            <span>${rating}</span>
            <a href="${escapeHtml(deal.message_link || '#')}" target="_blank" rel="noopener" class="deal-title">${escapeHtml(deal.chat_title || 'قناة')}</a>
            <span class="deal-time">${new Date(deal.received_at || Date.now()).toLocaleTimeString('ar-EG-u-nu-latn')}</span>
        </div>
        <div class="deal-body">
            <span>مطلوب: <b>${asked}</b></span>
            <span>عادل: <b>${NF.format(deal.fair_value || 0)}</b></span>
            <span>مكسب: <b class="${(deal.profit || 0) > 0 ? 'color-green' : 'color-red'}">${profit}</b></span>
        </div>`;
    feed.prepend(div);
    while (feed.children.length > 30) feed.lastChild.remove();
    refreshIcons(div);
}

function initLiveFeed() {
    if (dealsSocket) return;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    try {
        dealsSocket = new WebSocket(`${proto}://${location.host}/ws/deals`);
    } catch (e) {
        console.error(e);
        return;
    }
    dealsSocket.onopen = () => setLiveFeedStatus(true);
    dealsSocket.onclose = () => { setLiveFeedStatus(false); dealsSocket = null; };
    dealsSocket.onerror = () => setLiveFeedStatus(false);
    dealsSocket.onmessage = ev => {
        try { appendDealCard(JSON.parse(ev.data)); } catch { /* ignore malformed frames */ }
    };
}

async function loadDealsTrust() {
    initLiveFeed();

    try {
        const rep = await (await fetch('/market/reposts')).json();
        const grid = document.getElementById('repostSummaryGrid');
        if (grid) {
            grid.innerHTML = `
                <div class="stat-card">
                    <span class="stat-k">حسابات فريدة</span>
                    <span class="stat-v">${rep.unique_accounts != null ? NF.format(rep.unique_accounts) : '—'}</span>
                    <span class="stat-s">من ${rep.total_listings != null ? NF.format(rep.total_listings) : '—'} إعلان</span>
                </div>
                <div class="stat-card">
                    <span class="stat-k">نسبة المُعاد نشرهم</span>
                    <span class="stat-v">${rep.repost_share_pct || 0}%</span>
                    <span class="stat-s">أعلى تكرار: ${rep.max_reposts_observed || 0} مرة</span>
                </div>
                <div class="stat-card">
                    <span class="stat-k">وسيط أيام العرض</span>
                    <span class="stat-v">${rep.median_days_on_market_reposted ?? '—'}</span>
                    <span class="stat-s">للحسابات المعاد نشرها</span>
                </div>
                <div class="stat-card">
                    <span class="stat-k">علامات تم البيع</span>
                    <span class="stat-v">${rep.sold_marker_accounts || 0}</span>
                    <span class="stat-s">حسابات تم بيعها فعلاً</span>
                </div>`;
        }

        const rows = (rep.top_reposts || []).map((t, i) => `
            <tr>
                <td>${i + 1}</td>
                <td><code>${escapeHtml(t.fingerprint)}</code></td>
                <td>${t.posts}</td>
                <td>${escapeHtml((t.channels || []).join(', '))}</td>
                <td>${t.days_on_market}</td>
                <td class="num">${t.price_first ? NF.format(t.price_first) : '—'} → ${t.price_last ? NF.format(t.price_last) : '—'}</td>
                <td>${t.still_listed ? '<span class="color-green">معروض</span>' : '<span class="color-red">مبيع</span>'}</td>
            </tr>`).join('');

        const tbl = document.getElementById('topRepostsTableContainer');
        if (tbl) {
            tbl.innerHTML = `<table class="data-table">
                <thead><tr><th>#</th><th>البصمة</th><th>مرات النشر</th><th>القنوات</th><th>أيام</th><th>مسار السعر</th><th>الحالة</th></tr></thead>
                <tbody>${rows || '<tr><td colspan="7" class="color-muted">لا توجد بيانات إعادة نشر.</td></tr>'}</tbody>
            </table>`;
        }
    } catch (err) {
        console.error('reposts error:', err);
    }

    try {
        const tr = await (await fetch('/market/channels/trust')).json();
        const gradeClass = g => ({ 'A+': 'color-green', A: 'color-green', B: 'color-gold', C: 'color-gold', D: 'color-red' }[g] || '');
        const rows = (tr.channels || []).map(c => `
            <tr>
                <td><b>${escapeHtml(c.channel)}</b></td>
                <td class="${gradeClass(c.grade)}"><b>${c.trust_score}</b> <span class="color-muted">(${escapeHtml(c.grade)})</span></td>
                <td>${NF.format(c.n_ads)}</td>
                <td>${(c.components.middleman_ratio * 100).toFixed(0)}%</td>
                <td>${(c.components.internal_linkage_ratio * 100).toFixed(0)}%</td>
                <td>${(c.components.spam_ratio * 100).toFixed(1)}%</td>
                <td>${(c.components.repost_flood_ratio * 100).toFixed(0)}%</td>
                <td>${c.stats.ads_per_week}/أسبوع</td>
            </tr>`).join('');

        const el = document.getElementById('trustTableContainer');
        if (el) {
            el.innerHTML = `<table class="data-table">
                <thead><tr><th>القناة</th><th>الثقة</th><th>إعلانات</th><th>وسيط</th><th>ربط داخلي</th><th>سبام</th><th>إعادة نشر</th><th>نشاط</th></tr></thead>
                <tbody>${rows || '<tr><td colspan="8" class="color-muted">لا توجد بيانات ثقة.</td></tr>'}</tbody>
            </table>`;
        }
    } catch (err) {
        console.error('trust error:', err);
    }
}
