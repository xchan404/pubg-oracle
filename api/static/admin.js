/* ==========================================================================
   PUBG ORACLE — ADMIN DASHBOARD
   Auth: X-Admin-Token (local token) or Telegram owner initData.
   Every figure comes from /api/admin/*. Unknown → "—".
   ========================================================================== */

const { icon, refreshIcons, fmt, escapeHtml, shortDate, numDate, toast, NF } = window.OracleUI;

const tg = window.Telegram?.WebApp;
if (tg) {
    try { tg.ready(); tg.expand(); } catch { /* older clients */ }
}
const initData = tg?.initData || '';

const TOKEN_KEY = 'oracle.admin.token';
const CURRENCY_LABEL = { EGP: 'ج.م', SAR: 'ر.س', AED: 'د.إ', USD: '$' };
const PROVIDER_LABEL = {
    vodafone_cash: 'فودافون كاش',
    instapay: 'إنستاباي',
    telegram_stars: 'نجوم تليجرام',
    manual: 'يدوي',
};
const STATUS_LABEL = { pending: 'قيد المراجعة', approved: 'مقبولة', rejected: 'مرفوضة' };
const PLAN_LABEL = {
    free: 'مجاني',
    pro_monthly: 'Pro شهري',
    pro_annual: 'Pro سنوي',
    business: 'Business',
};

let adminToken = localStorage.getItem(TOKEN_KEY) || '';
let currentView = 'overview';
let paymentStatus = 'pending';
let usersQuery = '';
let pendingCount = 0;

/* Local convenience: /admin#token=<token> logs in once and strips the fragment
   so the secret never sits in history or a bookmark. Localhost only. */
(function tokenFromFragment() {
    const isLocal = ['localhost', '127.0.0.1', '::1'].includes(location.hostname);
    const match = /(?:^#|&)token=([^&]+)/.exec(location.hash || '');
    if (!isLocal || !match) return;
    adminToken = decodeURIComponent(match[1]);
    localStorage.setItem(TOKEN_KEY, adminToken);
    history.replaceState(null, '', location.pathname);
})();

/* ── API ────────────────────────────────────────────────────────────────── */

async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (adminToken) headers['X-Admin-Token'] = adminToken;
    if (initData) headers['X-Telegram-Init-Data'] = initData;

    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const body = await response.json();
            if (body && body.detail) detail = body.detail;
        } catch { /* non-JSON error body */ }
        if (response.status === 401) {
            const err = new Error(detail);
            err.unauthorized = true;
            throw err;
        }
        throw new Error(detail);
    }
    return response.json();
}

function postJson(path, body) {
    return api(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
    });
}

/* ── Boot ───────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', async () => {
    refreshIcons();
    document.getElementById('loginForm').addEventListener('submit', onLogin);
    document.getElementById('logoutBtn').addEventListener('click', logout);
    document.getElementById('paymentFilter').addEventListener('click', onFilterClick);
    document.getElementById('userSearchBtn').addEventListener('click', onUserSearch);
    document.getElementById('userSearch').addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); onUserSearch(); }
    });
    document.querySelectorAll('.side-btn').forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.getAttribute('data-view')));
    });
    document.getElementById('refreshOverview').addEventListener('click', loadOverview);
    document.getElementById('refreshPayments').addEventListener('click', loadPayments);
    document.getElementById('refreshUsers').addEventListener('click', () => loadUsers(usersQuery));
    document.getElementById('refreshPartners').addEventListener('click', loadPartners);
    document.getElementById('refreshData').addEventListener('click', loadData);
    document.getElementById('retrainBtn').addEventListener('click', onRetrain);

    await restoreSession();
});

async function restoreSession() {
    // Telegram owner: initData is enough, no token needed.
    if (initData) {
        try {
            await api('/api/admin/session');
            showApp();
            return;
        } catch (err) {
            if (!err.unauthorized) {
                toast(err.message, true);
            }
        }
    }

    if (adminToken) {
        try {
            await api('/api/admin/session');
            showApp();
            return;
        } catch {
            localStorage.removeItem(TOKEN_KEY);
            adminToken = '';
        }
    }

    showLogin();
}

async function onLogin(event) {
    event.preventDefault();
    const input = document.getElementById('adminToken');
    const token = input.value.trim();
    if (!token) {
        toast('أدخل توكن الإدارة أولًا', true);
        return;
    }

    const btn = event.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    const previous = adminToken;
    adminToken = token;
    try {
        await api('/api/admin/session');
        localStorage.setItem(TOKEN_KEY, token);
        input.value = '';
        showApp();
    } catch (err) {
        adminToken = previous;
        toast(err.unauthorized ? 'توكن غير صحيح' : err.message, true);
    } finally {
        btn.disabled = false;
    }
}

function logout() {
    localStorage.removeItem(TOKEN_KEY);
    adminToken = '';
    showLogin();
}

function showLogin() {
    document.getElementById('adminApp').classList.add('hidden');
    document.getElementById('logoutBtn').classList.add('hidden');
    document.getElementById('adminLogin').classList.remove('hidden');
    refreshIcons();
}

function showApp() {
    document.getElementById('adminLogin').classList.add('hidden');
    document.getElementById('adminApp').classList.remove('hidden');
    document.getElementById('logoutBtn').classList.remove('hidden');
    refreshIcons();

    const requested = new URLSearchParams(location.search).get('view');
    if (requested && document.getElementById(`view-${requested}`)) {
        switchView(requested);
    } else {
        loadOverview();
    }
}

function handleAuthError(err) {
    if (err && err.unauthorized) {
        showLogin();
        return true;
    }
    return false;
}

/* ── Navigation ─────────────────────────────────────────────────────────── */

function switchView(view) {
    if (!view) return;
    currentView = view;
    document.querySelectorAll('.side-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-view') === view);
    });
    document.querySelectorAll('.view').forEach(section => {
        section.classList.toggle('active', section.id === `view-${view}`);
    });
    refreshIcons();

    const loaders = {
        overview: loadOverview,
        payments: loadPayments,
        users: () => loadUsers(usersQuery),
        partners: loadPartners,
        data: loadData,
    };
    (loaders[view] || loadOverview)();
}

/* ── Overview ───────────────────────────────────────────────────────────── */

async function loadOverview() {
    const btn = document.getElementById('refreshOverview');
    btn?.classList.add('is-spinning');
    try {
        const data = await api('/api/admin/overview');
        renderOverview(data);
    } catch (err) {
        if (!handleAuthError(err)) toast(err.message || 'تعذر تحميل النظرة العامة', true);
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

function moneyLines(rows) {
    if (!rows || !rows.length) return { main: '—', rest: '' };
    const sorted = [...rows].sort((a, b) => Number(b.amount) - Number(a.amount));
    const head = sorted[0];
    const label = code => CURRENCY_LABEL[code] || code;
    return {
        main: `${NF.format(Math.round(Number(head.amount)))} ${label(head.currency)}`,
        rest: sorted.slice(1)
            .map(r => `${NF.format(Math.round(Number(r.amount)))} ${label(r.currency)}`)
            .join(' · '),
    };
}

function renderOverview(data) {
    const users = data.users || {};
    const payments = data.payments || {};
    const fresh = data.freshness || {};

    pendingCount = payments.pending || 0;
    renderPendingBadge();

    /* Freshness banner */
    const note = document.getElementById('freshnessNote');
    const stale = !!fresh.is_stale;
    note.className = `inline-note ${stale ? 'is-warn' : 'is-ok'}`;
    if (stale) {
        const hours = Number(fresh.hours_since_last);
        const days = Number.isFinite(hours) ? Math.max(1, Math.round(hours / 24)) : null;
        note.innerHTML = `${icon('triangle-alert')}<span>البيانات متأخرة${days ? ` ${days} يوم` : ''} — لا تفتح بيعًا مدفوعًا قبل 7 أيام بيانات حديثة. آخر إعلان: ${shortDate(fresh.last_listing_at)}.</span>`;
    } else {
        note.innerHTML = `${icon('circle-check')}<span>البيانات حديثة — آخر إعلان ${shortDate(fresh.last_listing_at)} (قبل ${Math.round(Number(fresh.hours_since_last) || 0)} ساعة).</span>`;
    }

    const monthMoney = moneyLines(data.revenue_month);
    const lifetimeMoney = moneyLines(data.revenue_lifetime);

    document.getElementById('overviewKpis').innerHTML = `
        <div class="kpi is-brand">
            <span class="kpi-k">إيراد الشهر</span>
            <span class="kpi-v ${monthMoney.rest ? 'is-money' : ''}">${monthMoney.main}</span>
            <span class="kpi-s">${monthMoney.rest ? `${monthMoney.rest} · هذا الشهر` : 'الدفعات المعتمدة هذا الشهر'}</span>
        </div>
        <div class="kpi">
            <span class="kpi-k">إجمالي الإيراد</span>
            <span class="kpi-v ${lifetimeMoney.rest ? 'is-money' : ''}">${lifetimeMoney.main}</span>
            <span class="kpi-s">${lifetimeMoney.rest ? `${lifetimeMoney.rest} · إجمالي` : 'من بداية التشغيل'}</span>
        </div>
        <div class="kpi">
            <span class="kpi-k">مستخدمون</span>
            <span class="kpi-v">${fmt(users.total)}</span>
            <span class="kpi-s">+${fmt(users.new_7d)} آخر 7 أيام</span>
        </div>
        <div class="kpi">
            <span class="kpi-k">اشتراكات نشطة</span>
            <span class="kpi-v">${fmt(users.paid_active)}</span>
            <span class="kpi-s">${fmt(data.expiring_3d)} تنتهي خلال 3 أيام</span>
        </div>
        <div class="kpi ${pendingCount ? 'is-warn' : ''}">
            <span class="kpi-k">دفعات معلّقة</span>
            <span class="kpi-v">${fmt(pendingCount)}</span>
            <span class="kpi-s">تحتاج قرارًا</span>
        </div>
        <div class="kpi">
            <span class="kpi-k">أرصدة استعلامات</span>
            <span class="kpi-v">${fmt(data.credits_outstanding)}</span>
            <span class="kpi-s">التزامات غير مستخدمة</span>
        </div>`;

    /* Recent payments */
    const recent = data.recent_payments || [];
    const recentWrap = document.getElementById('recentPayments');
    if (!recent.length) {
        recentWrap.innerHTML = '<p class="empty-row">لا توجد مدفوعات بعد.</p>';
    } else {
        recentWrap.innerHTML = `
            <table class="data-table">
                <thead><tr><th>#</th><th>المستخدم</th><th>المبلغ</th><th>الحالة</th><th>التاريخ</th></tr></thead>
                <tbody>${recent.map(p => `
                    <tr>
                        <td>#${p.id}</td>
                        <td>${userCell(p.user)}</td>
                        <td class="amount">${amountCell(p)}</td>
                        <td class="${statusClass(p.status)}"><span class="status-dot ${escapeHtml(p.status)}"></span>${escapeHtml(STATUS_LABEL[p.status] || p.status)}</td>
                        <td class="nowrap" dir="ltr">${numDate(p.created_at, true)}</td>
                    </tr>`).join('')}</tbody>
            </table>`;
    }

    /* Partner mini table */
    const partners = data.partners || [];
    const partnerWrap = document.getElementById('partnerMini');
    if (!partners.length) {
        partnerWrap.innerHTML = '<p class="empty-row">لا توجد مبيعات مرتبطة بشركاء بعد.</p>';
    } else {
        partnerWrap.innerHTML = `
            <table class="data-table">
                <thead><tr><th>الكود</th><th>مبيعات</th><th>حصة 25%</th><th>عدد</th></tr></thead>
                <tbody>${partners.map(p => `
                    <tr>
                        <td><code>${escapeHtml(p.code || '—')}</code></td>
                        <td class="amount">${fmt(p.gross)}</td>
                        <td class="amount color-gold">${fmt(p.share)}</td>
                        <td>${fmt(p.payments)}</td>
                    </tr>`).join('')}</tbody>
            </table>`;
    }

    refreshIcons();
}

function renderPendingBadge() {
    const badge = document.getElementById('pendingCount');
    if (!badge) return;
    badge.textContent = pendingCount > 99 ? '99+' : String(pendingCount);
    badge.classList.toggle('hidden', !pendingCount);
}

/* ── Payments ───────────────────────────────────────────────────────────── */

function onFilterClick(event) {
    const btn = event.target.closest('button[data-status]');
    if (!btn) return;
    paymentStatus = btn.getAttribute('data-status');
    document.querySelectorAll('#paymentFilter button').forEach(b => {
        b.classList.toggle('active', b === btn);
    });
    loadPayments();
}

async function loadPayments() {
    const btn = document.getElementById('refreshPayments');
    btn?.classList.add('is-spinning');
    const wrap = document.getElementById('paymentsBody');
    try {
        const data = await api(`/api/admin/payments?status=${encodeURIComponent(paymentStatus)}`);
        const items = data.items || [];
        const counts = data.counts || {};
        pendingCount = counts.pending || 0;
        renderPendingBadge();

        if (!items.length) {
            wrap.innerHTML = `<p class="empty-row">لا توجد دفعات في هذه الحالة.</p>`;
            return;
        }

        wrap.innerHTML = `
            <table class="data-table">
                <thead><tr>
                    <th>#</th><th>المستخدم</th><th>الخطة</th><th>المبلغ</th>
                    <th>الوسيلة</th><th>الحالة</th><th>التاريخ</th><th>إجراءات</th>
                </tr></thead>
                <tbody>${items.map(p => `
                    <tr>
                        <td>#${p.id}</td>
                        <td>${userCell(p.user)}</td>
                        <td>${escapeHtml(p.offer_code ? (PLAN_LABEL[p.offer_code] || p.offer_code) : '—')}</td>
                        <td class="amount">${amountCell(p)}</td>
                        <td>${escapeHtml(PROVIDER_LABEL[p.provider] || p.provider)}</td>
                        <td class="${statusClass(p.status)}"><span class="status-dot ${escapeHtml(p.status)}"></span>${escapeHtml(STATUS_LABEL[p.status] || p.status)}</td>
                        <td class="nowrap" dir="ltr">${numDate(p.created_at, true)}</td>
                        <td>${actionButtons(p)}</td>
                    </tr>`).join('')}</tbody>
            </table>`;

        wrap.querySelectorAll('[data-action]').forEach(el => {
            el.addEventListener('click', () => {
                const id = Number(el.getAttribute('data-id'));
                const payment = items.find(p => p.id === id);
                if (!payment) return;
                if (el.getAttribute('data-action') === 'approve') openApprove(payment);
                else openReject(payment);
            });
        });
        refreshIcons(wrap);
    } catch (err) {
        if (!handleAuthError(err)) toast(err.message || 'تعذر تحميل المدفوعات', true);
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

function actionButtons(payment) {
    if (payment.status !== 'pending') {
        return `<span class="muted-note">${escapeHtml(payment.reviewed_by || '—')}</span>`;
    }
    return `<div class="table-actions">
        <button type="button" class="btn btn-ghost btn-xs" data-action="approve" data-id="${payment.id}">
            ${icon('check')} اعتماد
        </button>
        <button type="button" class="btn btn-ghost btn-xs" data-action="reject" data-id="${payment.id}">
            ${icon('x')} رفض
        </button>
    </div>`;
}

function openApprove(payment) {
    const inferred = payment.offer_code ? (PLAN_LABEL[payment.offer_code] || payment.offer_code) : 'غير محدد';
    openModal({
        title: `اعتماد الدفعة #${payment.id}`,
        subtitle: `${userName(payment.user)} · ${NF.format(Math.round(payment.amount))} ${CURRENCY_LABEL[payment.currency] || payment.currency}`,
        body: `
            <div class="inline-note">
                ${icon('info')}
                <span>الخطة المرتبطة بالدفعة: <b>${escapeHtml(inferred)}</b>.
                الاعتماد يفعّل الاشتراك فورًا ويحسب حصة الشريك إن وجدت.</span>
            </div>
            <div class="field-inline">
                <label for="approvePlan">تجاوز الخطة (اختياري)</label>
                <select id="approvePlan">
                    <option value="">استخدام خطة الدفعة</option>
                    <option value="pro_monthly">Pro شهري</option>
                    <option value="pro_annual">Pro سنوي</option>
                    <option value="business">Business</option>
                </select>
            </div>
            <div class="field-inline">
                <label for="approveDays">عدد الأيام (اختياري)</label>
                <input id="approveDays" type="number" min="1" max="730" placeholder="30">
            </div>`,
        confirmLabel: 'اعتماد وتفعيل',
        onConfirm: async () => {
            const plan = document.getElementById('approvePlan').value || null;
            const daysRaw = document.getElementById('approveDays').value.trim();
            await postJson(`/api/admin/payments/${payment.id}/approve`, {
                plan,
                days: daysRaw ? Number(daysRaw) : null,
            });
            toast(`تم اعتماد الدفعة #${payment.id}`);
            loadPayments();
            if (currentView === 'overview') loadOverview();
        },
    });
}

function openReject(payment) {
    openModal({
        title: `رفض الدفعة #${payment.id}`,
        subtitle: `${userName(payment.user)} · ${NF.format(Math.round(payment.amount))} ${CURRENCY_LABEL[payment.currency] || payment.currency}`,
        body: `
            <div class="inline-note is-warn">
                ${icon('triangle-alert')}
                <span>الرفض لا يفعّل أي شيء. اكتب سببًا واضحًا ليظهر في سجل الدفعة.</span>
            </div>
            <div class="field-inline">
                <label for="rejectReason">السبب</label>
                <textarea id="rejectReason" placeholder="مثال: لم يصل التحويل / إثبات مكرر"></textarea>
            </div>`,
        confirmLabel: 'رفض الدفعة',
        danger: true,
        onConfirm: async () => {
            const reason = document.getElementById('rejectReason').value.trim();
            await postJson(`/api/admin/payments/${payment.id}/reject`, { reason: reason || null });
            toast(`تم رفض الدفعة #${payment.id}`);
            loadPayments();
            if (currentView === 'overview') loadOverview();
        },
    });
}

/* ── Users ──────────────────────────────────────────────────────────────── */

function onUserSearch() {
    usersQuery = document.getElementById('userSearch').value.trim();
    loadUsers(usersQuery);
}

async function loadUsers(query) {
    const btn = document.getElementById('refreshUsers');
    btn?.classList.add('is-spinning');
    const wrap = document.getElementById('usersBody');
    try {
        const data = await api(`/api/admin/users?query=${encodeURIComponent(query || '')}&limit=100`);
        const items = data.items || [];
        document.getElementById('usersTotal').textContent =
            `${fmt(data.total)} مستخدم إجمالًا — يُعرض ${fmt(items.length)}`;

        if (!items.length) {
            wrap.innerHTML = '<p class="empty-row">لا نتائج مطابقة.</p>';
            return;
        }

        wrap.innerHTML = `
            <table class="data-table">
                <thead><tr>
                    <th>المستخدم</th><th>الخطة</th><th>استخدام 24س</th>
                    <th>رصيد</th><th>السوق</th><th>الحالة</th><th>إجراءات</th>
                </tr></thead>
                <tbody>${items.map(u => `
                    <tr>
                        <td>${userCell(u)}</td>
                        <td>
                            <span class="badge ${u.plan && u.plan.is_paid ? 'badge-green' : 'badge-muted'}">
                                ${escapeHtml((u.plan && u.plan.label) || 'مجاني')}
                            </span>
                        </td>
                        <td class="amount">${u.plan && u.plan.checks_per_day == null ? '∞' : `${fmt(u.checks_used_24h)} / ${fmt(u.plan && u.plan.checks_per_day)}`}</td>
                        <td class="amount">${fmt(u.credits)}</td>
                        <td>${escapeHtml(u.currency || '—')}${u.country ? `<span class="muted-note"> · ${escapeHtml(u.country)}</span>` : ''}</td>
                        <td>${u.is_banned ? '<span class="color-red">محظور</span>' : '<span class="color-green">نشط</span>'}</td>
                        <td>
                            <div class="table-actions">
                                <button type="button" class="btn btn-ghost btn-xs" data-user-action="grant" data-id="${u.id}">
                                    ${icon('crown')} خطة
                                </button>
                                <button type="button" class="btn btn-ghost btn-xs" data-user-action="credits" data-id="${u.id}">
                                    ${icon('plus')} رصيد
                                </button>
                                <button type="button" class="btn btn-ghost btn-xs" data-user-action="ban" data-id="${u.id}">
                                    ${icon(u.is_banned ? 'unlock' : 'ban')} ${u.is_banned ? 'فك الحظر' : 'حظر'}
                                </button>
                            </div>
                        </td>
                    </tr>`).join('')}</tbody>
            </table>`;

        wrap.querySelectorAll('[data-user-action]').forEach(el => {
            el.addEventListener('click', () => {
                const id = Number(el.getAttribute('data-id'));
                const user = items.find(u => u.id === id);
                if (!user) return;
                const action = el.getAttribute('data-user-action');
                if (action === 'grant') openGrant(user);
                else if (action === 'credits') openCredits(user);
                else openBan(user);
            });
        });
        refreshIcons(wrap);
    } catch (err) {
        if (!handleAuthError(err)) toast(err.message || 'تعذر تحميل المستخدمين', true);
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

function openGrant(user) {
    openModal({
        title: `منح خطة — ${userName(user)}`,
        subtitle: `الخطة الحالية: ${(user.plan && user.plan.label) || 'مجاني'}`,
        body: `
            <div class="field-inline">
                <label for="grantPlan">الخطة</label>
                <select id="grantPlan">
                    <option value="pro_monthly">Pro شهري</option>
                    <option value="pro_annual">Pro سنوي</option>
                    <option value="business">Business</option>
                </select>
            </div>
            <div class="field-inline">
                <label for="grantDays">المدة بالأيام</label>
                <input id="grantDays" type="number" min="1" max="730" value="30">
            </div>
            <div class="inline-note">
                ${icon('info')}
                <span>المنح اليدوي يُسجَّل باسم admin ويظهر للمستخدم في لوحته.</span>
            </div>`,
        confirmLabel: 'منح الخطة',
        onConfirm: async () => {
            const plan = document.getElementById('grantPlan').value;
            const days = Number(document.getElementById('grantDays').value || 30);
            await postJson(`/api/admin/users/${user.id}/grant`, { plan, days });
            toast(`تم منح ${PLAN_LABEL[plan] || plan} لـ ${userName(user)}`);
            loadUsers(usersQuery);
        },
    });
}

function openCredits(user) {
    openModal({
        title: `تعديل الرصيد — ${userName(user)}`,
        subtitle: `الرصيد الحالي: ${fmt(user.credits)} استعلام`,
        body: `
            <div class="field-inline">
                <label for="creditAmount">عدد الاستعلامات (+ لإضافة، − لخصم)</label>
                <input id="creditAmount" type="number" step="1" placeholder="5">
            </div>
            <div class="field-inline">
                <label for="creditReason">السبب</label>
                <input id="creditReason" type="text" value="admin_adjustment">
            </div>`,
        confirmLabel: 'تطبيق',
        onConfirm: async () => {
            const raw = document.getElementById('creditAmount').value.trim();
            const amount = Number(raw);
            if (!raw || !Number.isFinite(amount) || amount === 0) {
                throw new Error('أدخل عددًا غير صفري');
            }
            const reason = document.getElementById('creditReason').value.trim() || 'admin_adjustment';
            const result = await postJson(`/api/admin/users/${user.id}/credits`, {
                amount: Math.trunc(amount),
                reason,
            });
            toast(`الرصيد الجديد: ${fmt(result.credits)}`);
            loadUsers(usersQuery);
        },
    });
}

function openBan(user) {
    const banning = !user.is_banned;
    openModal({
        title: `${banning ? 'حظر' : 'فك حظر'} — ${userName(user)}`,
        subtitle: `Telegram ID ${user.telegram_id ?? '—'}`,
        body: `
            <div class="inline-note ${banning ? 'is-warn' : ''}">
                ${icon(banning ? 'triangle-alert' : 'info')}
                <span>${banning
                    ? 'المستخدم المحظور لا يستطيع تنفيذ استعلامات مدفوعة أو مجانية.'
                    : 'فك الحظر يعيد الوصول حسب الخطة الحالية.'}</span>
            </div>`,
        confirmLabel: banning ? 'حظر المستخدم' : 'فك الحظر',
        danger: banning,
        onConfirm: async () => {
            await postJson(`/api/admin/users/${user.id}/ban`, { banned: banning });
            toast(banning ? 'تم حظر المستخدم' : 'تم فك الحظر');
            loadUsers(usersQuery);
        },
    });
}

/* ── Partners ───────────────────────────────────────────────────────────── */

async function loadPartners() {
    const btn = document.getElementById('refreshPartners');
    btn?.classList.add('is-spinning');
    const wrap = document.getElementById('partnersBody');
    try {
        const data = await api('/api/admin/partners');
        const items = data.items || [];
        if (!items.length) {
            wrap.innerHTML = '<p class="empty-row">لا توجد مبيعات مرتبطة بشركاء بعد.</p>';
            return;
        }
        const totalGross = items.reduce((sum, p) => sum + Number(p.gross || 0), 0);
        const totalShare = items.reduce((sum, p) => sum + Number(p.share || 0), 0);

        wrap.innerHTML = `
            <table class="data-table">
                <thead><tr>
                    <th>كود الشريك</th><th>إجمالي المبيعات</th><th>حصة الشريك (25%)</th>
                    <th>عدد الدفعات</th><th>متوسط الدفعة</th>
                </tr></thead>
                <tbody>
                    ${items.map(p => `
                        <tr>
                            <td><code>${escapeHtml(p.code || '—')}</code></td>
                            <td class="amount">${fmt(p.gross)}</td>
                            <td class="amount color-gold">${fmt(p.share)}</td>
                            <td>${fmt(p.payments)}</td>
                            <td class="amount">${p.payments ? fmt(Math.round((Number(p.gross) / p.payments) * 100) / 100) : '—'}</td>
                        </tr>`).join('')}
                    <tr>
                        <td><b>الإجمالي</b></td>
                        <td class="amount"><b>${fmt(Math.round(totalGross * 100) / 100)}</b></td>
                        <td class="amount color-gold"><b>${fmt(Math.round(totalShare * 100) / 100)}</b></td>
                        <td><b>${fmt(items.reduce((s, p) => s + Number(p.payments || 0), 0))}</b></td>
                        <td>—</td>
                    </tr>
                </tbody>
            </table>`;
        refreshIcons(wrap);
    } catch (err) {
        if (!handleAuthError(err)) toast(err.message || 'تعذر تحميل الشركاء', true);
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

/* ── Data & system ──────────────────────────────────────────────────────── */

async function loadData() {
    const btn = document.getElementById('refreshData');
    btn?.classList.add('is-spinning');
    try {
        const data = await api('/api/admin/data');
        const fresh = data.freshness || {};
        const counts = data.counts || {};
        const stale = !!fresh.is_stale;
        const hours = Number(fresh.hours_since_last);
        const days = Number.isFinite(hours) ? Math.max(1, Math.round(hours / 24)) : null;

        document.getElementById('dataKpis').innerHTML = `
            <div class="kpi ${stale ? 'is-warn' : 'is-ok'}">
                <span class="kpi-k">حالة البيانات</span>
                <span class="kpi-v is-text">${stale ? 'متأخرة' : 'حديثة'}</span>
                <span class="kpi-s">${stale ? `قبل ${days || '—'} يوم` : `قبل ${Math.round(hours || 0)} ساعة`}</span>
            </div>
            <div class="kpi">
                <span class="kpi-k">آخر إعلان</span>
                <span class="kpi-v is-text">${shortDate(fresh.last_listing_at)}</span>
                <span class="kpi-s">أحدث سجل في القاعدة</span>
            </div>
            <div class="kpi">
                <span class="kpi-k">إجمالي الإعلانات</span>
                <span class="kpi-v">${fmt(fresh.listings_total)}</span>
                <span class="kpi-s">كل ما تم تحليله</span>
            </div>
            <div class="kpi">
                <span class="kpi-k">مستخدمون / مدفوعات</span>
                <span class="kpi-v">${fmt(counts.users)} / ${fmt(counts.payments)}</span>
                <span class="kpi-s">اشتراكات نشطة: ${fmt(counts.active_subscriptions)}</span>
            </div>`;

        const note = document.getElementById('dataNote');
        note.className = 'inline-note';
        note.innerHTML = `${icon('key-round')}<span>مسار توكن الإدارة: <code dir="ltr">${escapeHtml(data.admin_token_path || '—')}</code></span>`;
        refreshIcons();
    } catch (err) {
        if (!handleAuthError(err)) toast(err.message || 'تعذر تحميل حالة البيانات', true);
    } finally {
        btn?.classList.remove('is-spinning');
    }
}

async function onRetrain() {
    const btn = document.getElementById('retrainBtn');
    btn.disabled = true;
    btn.classList.add('is-spinning');
    try {
        const result = await postJson('/api/admin/retrain', {});
        toast(result.message || 'تم إطلاق إعادة التدريب');
        loadData();
    } catch (err) {
        if (!handleAuthError(err)) toast(err.message || 'فشل إعادة التدريب', true);
    } finally {
        btn.disabled = false;
        btn.classList.remove('is-spinning');
    }
}

/* ── Shared cells ───────────────────────────────────────────────────────── */

function userName(user) {
    if (!user) return '—';
    return user.first_name || (user.username ? `@${user.username}` : `ID ${user.telegram_id ?? '—'}`);
}

function userCell(user) {
    if (!user) return '<span class="muted-note">—</span>';
    const name = escapeHtml(userName(user));
    const handle = user.username ? `@${escapeHtml(user.username)}` : `ID ${escapeHtml(String(user.telegram_id ?? '—'))}`;
    return `<div class="row-user"><b>${name}</b><span>${handle}</span></div>`;
}

function amountCell(payment) {
    const value = Number(payment.amount);
    if (!Number.isFinite(value)) return '—';
    return `${NF.format(Math.round(value))} ${CURRENCY_LABEL[payment.currency] || payment.currency || ''}`;
}

function statusClass(status) {
    if (status === 'approved') return 'color-green';
    if (status === 'rejected') return 'color-red';
    return 'color-gold';
}

/* ── Modal ──────────────────────────────────────────────────────────────── */

let modalClose = null;

function openModal({ title, subtitle, body, confirmLabel, onConfirm, danger = false }) {
    closeModal();
    const root = document.getElementById('modalRoot');
    root.innerHTML = `
        <div class="modal-backdrop">
            <form class="modal" novalidate>
                <h2>${escapeHtml(title)}</h2>
                ${subtitle ? `<p class="panel-sub">${escapeHtml(subtitle)}</p>` : ''}
                <div class="modal-body">${body}</div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-ghost" data-modal="cancel">إلغاء</button>
                    <button type="submit" class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-modal="confirm">
                        ${escapeHtml(confirmLabel || 'تأكيد')}
                    </button>
                </div>
            </form>
        </div>`;

    const form = root.querySelector('form');
    const confirmBtn = root.querySelector('[data-modal="confirm"]');
    const cancelBtn = root.querySelector('[data-modal="cancel"]');

    cancelBtn.addEventListener('click', closeModal);
    root.querySelector('.modal-backdrop').addEventListener('click', event => {
        if (event.target === event.currentTarget) closeModal();
    });

    const onKey = event => { if (event.key === 'Escape') closeModal(); };
    document.addEventListener('keydown', onKey);

    form.addEventListener('submit', async event => {
        event.preventDefault();
        confirmBtn.disabled = true;
        confirmBtn.classList.add('is-spinning');
        try {
            await onConfirm();
            closeModal();
        } catch (err) {
            toast(err.message || 'تعذر تنفيذ الإجراء', true);
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('is-spinning');
        }
    });

    modalClose = () => {
        document.removeEventListener('keydown', onKey);
        root.innerHTML = '';
        modalClose = null;
    };

    refreshIcons(root);
    root.querySelector('input, select, textarea')?.focus();
}

function closeModal() {
    if (modalClose) modalClose();
}
