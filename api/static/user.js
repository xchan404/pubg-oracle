/* ==========================================================================
   PUBG ORACLE — SUBSCRIBER DASHBOARD
   Auth: Telegram WebApp initData. No initData → friendly gate, never fake data.
   ========================================================================== */

const { icon, refreshIcons, fmt, escapeHtml, shortDate, numDate, toast, NF } = window.OracleUI;

const tg = window.Telegram?.WebApp;
if (tg) {
    try { tg.ready(); tg.expand(); } catch { /* older clients */ }
}
const initData = tg?.initData || '';

/* Local preview: /dashboard?dev=1201 impersonates a seeded user while
   DASHBOARD_DEV_LOGIN=1 on the server. Never set in production. */
const DEV_KEY = 'oracle.dev.telegram_id';
const devFromUrl = new URLSearchParams(location.search).get('dev');
if (devFromUrl) {
    sessionStorage.setItem(DEV_KEY, devFromUrl);
    const clean = new URL(location.href);
    clean.searchParams.delete('dev');
    history.replaceState(null, '', clean.pathname + clean.search + clean.hash);
}
const devId = sessionStorage.getItem(DEV_KEY) || '';

const CURRENCY_LABEL = { EGP: 'ج.م', SAR: 'ر.س', AED: 'د.إ' };
const PROVIDER_LABEL = {
    vodafone_cash: 'فودافون كاش',
    instapay: 'إنستاباي',
    telegram_stars: 'نجوم تليجرام',
    manual: 'يدوي',
};
const STATUS_LABEL = { pending: 'قيد المراجعة', approved: 'مقبول', rejected: 'مرفوض' };

async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (initData) headers['X-Telegram-Init-Data'] = initData;
    else if (devId) headers['X-Dev-Telegram-Id'] = devId;
    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const body = await response.json();
            if (body && body.detail) detail = body.detail;
        } catch { /* non-JSON error */ }
        throw new Error(detail);
    }
    return response.json();
}

async function boot() {
    refreshIcons();

    if (!initData && !devId) {
        document.getElementById('userGate').classList.remove('hidden');
        refreshIcons();
        try {
            const config = await api('/api/config');
            const link = document.getElementById('botLink');
            if (config.bot_username) {
                link.href = `https://t.me/${config.bot_username}`;
                link.classList.remove('hidden');
                refreshIcons();
            }
        } catch { /* the gate text still explains what to do */ }
        return;
    }

    document.getElementById('userApp').classList.remove('hidden');
    document.getElementById('refreshMe').addEventListener('click', loadMe);
    document.getElementById('countrySelect').addEventListener('change', changeCountry);
    await loadMe();
}

let lastData = null;

async function loadMe() {
    const btn = document.getElementById('refreshMe');
    btn?.classList.add('is-spinning');
    try {
        lastData = await api('/api/me');
        render(lastData);
    } catch (err) {
        if (String(err.message).includes('افتح')) {
            document.getElementById('userApp').classList.add('hidden');
            document.getElementById('userGate').classList.remove('hidden');
            refreshIcons();
        } else {
            toast(err.message || 'تعذر تحميل بيانات الحساب', true);
        }
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

function render(data) {
    const u = data.user || {};
    const plan = data.plan || {};
    const usage = data.usage || {};
    const paid = !!plan.is_paid;
    const limit = usage.limit;
    const used = usage.used_24h || 0;

    const name = u.first_name || u.username || `مستخدم ${u.telegram_id ?? ''}`;
    document.getElementById('uAvatar').textContent = (name || '؟').trim().charAt(0);
    document.getElementById('uName').textContent = name;
    document.getElementById('uHandle').textContent = u.username
        ? `@${u.username}`
        : `ID ${u.telegram_id ?? '—'}`;

    const badge = document.getElementById('uPlanBadge');
    badge.textContent = plan.label || 'مجاني';
    badge.className = `badge ${paid ? 'badge-green' : 'badge-muted'}`;

    document.getElementById('uPlan').textContent = plan.label || 'مجاني';
    document.getElementById('uPlanSub').textContent = paid
        ? `ينتهي ${shortDate(plan.expires_at)} · متبقي ${plan.days_left ?? 0} يوم`
        : '3 استعلامات كل 24 ساعة';

    document.getElementById('uUsage').textContent = limit == null
        ? `${used} / ∞`
        : `${used} / ${limit}`;
    document.getElementById('uUsageSub').textContent = limit == null
        ? 'بلا حدود على خطتك'
        : usage.remaining != null
            ? `متبقي ${usage.remaining} استعلام`
            : '—';

    document.getElementById('uCredits').textContent = fmt(data.credits ?? 0);
    document.getElementById('uSince').textContent = shortDate(u.created_at);
    document.getElementById('uRef').textContent = u.referred_by
        ? `دعوة من: ${u.referred_by}`
        : 'بدون كود إحالة';

    /* Usage bar */
    const fill = document.getElementById('usageFill');
    const number = document.getElementById('usageNumber');
    const hint = document.getElementById('usageHint');
    if (limit == null) {
        number.textContent = `${used} / ∞`;
        fill.style.width = '100%';
        fill.className = 'usage-fill';
        hint.innerHTML = `${icon('infinity')}<span>خطتك تسمح باستعلامات غير محدودة. كل استعلام يُسجَّل في سجلك.</span>`;
    } else {
        const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
        number.textContent = `${used} / ${limit}`;
        fill.style.width = `${pct}%`;
        fill.className = 'usage-fill' + (used >= limit ? ' is-full' : used >= limit - 1 ? ' is-warn' : '');
        hint.innerHTML = used >= limit
            ? `${icon('triangle-alert')}<span>استهلكت الحد المجاني. يمكنك شراء استعلامات إضافية أو الترقية إلى Pro.</span>`
            : `${icon('info')}<span>يتجدد الحد تلقائيًا كل 24 ساعة متحركة من أول استعلام.</span>`;
    }

    /* Country */
    const countrySelect = document.getElementById('countrySelect');
    if (u.country) countrySelect.value = u.country;

    renderPayments(data.payments || []);
    renderOffers(data.offers || [], u.currency || 'EGP', data.bot_username || '');
    refreshIcons();
}

function renderPayments(payments) {
    const container = document.getElementById('paymentsTable');
    if (!payments.length) {
        container.innerHTML = '<p class="empty-row">لا توجد مدفوعات بعد.</p>';
        return;
    }

    const rows = payments.map(p => {
        const status = STATUS_LABEL[p.status] || p.status;
        const cls = p.status === 'approved' ? 'color-green' : p.status === 'rejected' ? 'color-red' : 'color-gold';
        return `<tr>
            <td>#${p.id}</td>
            <td>${escapeHtml(p.offer_code || '—')}</td>
            <td class="amount">${NF.format(Math.round(p.amount))} ${CURRENCY_LABEL[p.currency] || p.currency}</td>
            <td>${escapeHtml(PROVIDER_LABEL[p.provider] || p.provider)}</td>
            <td class="${cls}"><span class="status-dot ${escapeHtml(p.status)}"></span>${escapeHtml(status)}</td>
            <td class="nowrap" dir="ltr">${numDate(p.created_at, true)}</td>
        </tr>`;
    }).join('');

    container.innerHTML = `
        <table class="data-table">
            <thead><tr>
                <th>#</th><th>الخطة</th><th>المبلغ</th><th>الوسيلة</th><th>الحالة</th><th>التاريخ</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

function renderOffers(offers, currency, botUsername) {
    const container = document.getElementById('offersGrid');
    if (!offers.length) {
        container.innerHTML = '<p class="empty-row">لا توجد خطط متاحة.</p>';
        return;
    }

    container.innerHTML = offers.map(offer => {
        const label = CURRENCY_LABEL[offer.currency] || offer.currency;
        const sub = offer.credits
            ? `${offer.credits} استعلام إضافي`
            : `${offer.days} يوم`;
        const featured = offer.code === 'pro_monthly';
        return `<div class="offer ${featured ? 'is-featured' : ''}">
            <span class="offer-title">${escapeHtml(offer.title_ar)}</span>
            <span class="offer-price">${NF.format(offer.price)} <small>${label}</small></span>
            <span class="offer-sub">${sub}</span>
            <div class="offer-code">
                <span>/pay ${escapeHtml(offer.code)}</span>
                <button type="button" class="btn btn-ghost btn-xs" data-copy="/pay ${escapeHtml(offer.code)}">
                    ${icon('copy')}
                </button>
            </div>
        </div>`;
    }).join('');

    container.querySelectorAll('[data-copy]').forEach(btn => {
        btn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(btn.getAttribute('data-copy'));
                toast(botUsername
                    ? `انسخ الأمر وابعته للبوت @${botUsername}`
                    : 'تم نسخ أمر الدفع — ابعته للبوت');
            } catch {
                toast('تعذر النسخ — اكتب الأمر يدويًا', true);
            }
        });
    });
}

async function changeCountry(event) {
    const country = event.target.value;
    try {
        const result = await api('/api/me/locale', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ country }),
        });
        toast(`تم تحديث السوق إلى ${result.currency}`);
        await loadMe();
    } catch (err) {
        toast(err.message || 'تعذر تحديث الدولة', true);
    }
}

boot();
