/* Shared helpers for the dashboard pages (user + admin). */
(function () {
    const NF = new Intl.NumberFormat('en-US');

    function icon(name, cls = '') {
        return `<i data-lucide="${name}" class="ico ${cls}"></i>`;
    }

    function refreshIcons(root = document) {
        if (!window.lucide || typeof window.lucide.createIcons !== 'function') {
            retryIconsLater();
            return;
        }
        const pascal = s => s.replace(/(^|-)([a-z0-9])/g, (_, __, c) => c.toUpperCase());
        const available = window.lucide.icons || {};
        root.querySelectorAll('[data-lucide]').forEach(el => {
            const name = el.getAttribute('data-lucide');
            if (!available[pascal(name)]) el.setAttribute('data-lucide', 'circle');
        });
        window.lucide.createIcons();
    }

    /* Lucide is deferred; a page can render before it arrives. Retry briefly. */
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

    function fmt(v) {
        if (v === null || v === undefined || v === '' || v === 'N/A') return '—';
        const n = Number(v);
        return Number.isFinite(n) ? NF.format(n) : String(v);
    }

    function escapeHtml(s) {
        return String(s ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function shortDate(value, withTime = false) {
        if (!value) return '—';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return '—';
        const opts = { day: 'numeric', month: 'short', year: 'numeric' };
        if (withTime) { opts.hour = '2-digit'; opts.minute = '2-digit'; opts.hour12 = false; }
        return new Intl.DateTimeFormat('ar-EG-u-nu-latn', opts).format(d);
    }

    /* Compact, unambiguous dates for dense tables. */
    function numDate(value, withTime = false) {
        if (!value) return '—';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return '—';
        const pad = n => String(n).padStart(2, '0');
        const base = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
        return withTime ? `${base} ${pad(d.getHours())}:${pad(d.getMinutes())}` : base;
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

    window.OracleUI = { NF, icon, refreshIcons, fmt, escapeHtml, shortDate, numDate, toast };
})();
