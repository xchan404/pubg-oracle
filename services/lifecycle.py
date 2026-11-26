"""
Subscription lifecycle (Week 3)

Daily housekeeping that keeps paid access honest:
  1. notify users whose plan just ran out,
  2. remind users whose plan ends within N days,
  3. mark those expired subscriptions as `expired`,
  4. send the operator a one-message digest.

Everything is deterministic given `now`, and the notifier is injected, so the
whole job is testable without Telegram or a real database.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import Payment, Subscription, UsageEvent, User
from services.catalog import DEFAULT_CURRENCY, OFFERS, resolve_price
from services.entitlements import expire_stale_subscriptions
from services.notifier import BotNotifier, owner_chat_id

SEND_INTERVAL_SECONDS = 0.05  # stay well under Telegram's ~30 msg/s


@dataclass(frozen=True)
class MaintenanceReport:
    expired: int
    reminded: int
    sent: int             # user-facing messages only (digest excluded)
    failed: int           # user-facing messages only
    skipped: int          # notifier disabled
    digest_sent: bool     # operator digest delivered

    @property
    def notified(self) -> int:
        return self.sent + self.failed


def _due_subscriptions(
    session: Session, now: datetime
) -> list[tuple[Subscription, User]]:
    """Active subscriptions whose expiry has passed (not yet marked expired)."""
    rows = session.execute(
        select(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .where(Subscription.status == "active", Subscription.expires_at <= now)
        .order_by(Subscription.expires_at.asc())
    )
    return [(sub, user) for sub, user in rows]


def _expiring_subscriptions(
    session: Session, now: datetime, within_days: int
) -> list[tuple[Subscription, User]]:
    limit = now + timedelta(days=within_days)
    rows = session.execute(
        select(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .where(
            Subscription.status == "active",
            Subscription.expires_at > now,
            Subscription.expires_at <= limit,
        )
        .order_by(Subscription.expires_at.asc())
    )
    return [(sub, user) for sub, user in rows]


def expiry_notice_text(user: User, sub: Subscription, currency: str) -> str:
    who = f" يا {escape(user.first_name)}" if user.first_name else ""
    pro = resolve_price(OFFERS["pro_monthly"], currency)
    return (
        f"⏳ <b>انتهى اشتراكك{who}</b>\n\n"
        f"خطة <b>{escape(sub.plan)}</b> انتهت. رجعت للخطة المجانية "
        "(3 استعلامات كل 24 ساعة).\n\n"
        f"للتجديد: <b>{pro:,.0f} {currency}</b> شهريًا\n"
        "اكتب /plans للتفاصيل أو /pay pro_monthly للتجديد فورًا.\n\n"
        "💡 نصيحة: التجديد قبل الانتهاء يحافظ على تنبيهاتك بدون انقطاع."
    )


def renewal_reminder_text(
    user: User, sub: Subscription, days_left: int, currency: str
) -> str:
    who = f" يا {escape(user.first_name)}" if user.first_name else ""
    pro = resolve_price(OFFERS["pro_monthly"], currency)
    when = "النهاردة" if days_left <= 0 else f"بعد {days_left} يوم"
    return (
        f"🔔 <b>اشتراكك ينتهي {when}{who}</b>\n\n"
        f"خطة <b>{escape(sub.plan)}</b> مستمرة لحد "
        f"<b>{sub.expires_at.strftime('%Y-%m-%d')}</b>.\n\n"
        f"للتجديد: <b>{pro:,.0f} {currency}</b>\n"
        "اكتب /pay pro_monthly — والتجديد بيتراكم فوق المدة المتبقية."
    )


def daily_digest_text(
    session: Session,
    report: MaintenanceReport,
    *,
    now: datetime,
    currency: str = DEFAULT_CURRENCY,
) -> str:
    since = now - timedelta(hours=24)

    new_users = session.scalar(
        select(func.count(User.id)).where(User.created_at >= since)
    ) or 0
    checks = session.scalar(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.kind == "check", UsageEvent.created_at >= since
        )
    ) or 0
    revenue = session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0)).where(
            Payment.status == "approved", Payment.reviewed_at >= since
        )
    ) or 0.0
    pending = session.scalar(
        select(func.count(Payment.id)).where(Payment.status == "pending")
    ) or 0
    active_subs = session.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active", Subscription.expires_at > now
        )
    ) or 0

    return (
        f"📊 <b>ملخص اليوم — {now.strftime('%Y-%m-%d')}</b>\n\n"
        f"👥 مستخدمين جدد (24س): <b>{new_users}</b>\n"
        f"🔍 استعلامات (24س): <b>{checks}</b>\n"
        f"💳 إيراد معتمد (24س): <b>{revenue:,.0f} {currency}</b>\n"
        f"🕓 مدفوعات معلّقة: <b>{pending}</b>\n"
        f"⭐ اشتراكات نشطة: <b>{active_subs}</b>\n"
        f"⏳ انتهت اليوم: <b>{report.expired}</b> | "
        f"تذكيرات تجديد: <b>{report.reminded}</b>\n"
        f"📨 رسائل: {report.sent} تم | {report.failed} فشل | {report.skipped} متخطاة"
    )


def run_daily_maintenance(
    session: Session,
    notifier: BotNotifier | None = None,
    *,
    now: datetime | None = None,
    reminder_days: int = 3,
    owner_chat: int | str | None = None,
    sleep: Callable[[float], None] | None = None,
    currency: str = DEFAULT_CURRENCY,
) -> MaintenanceReport:
    """
    Sends expiry notices + renewal reminders, then expires the plans.

    Notices are sent *before* the status flips so users get a clear "your plan
    ended" message instead of silently losing access.
    """
    now = now or datetime.utcnow()
    notifier = notifier or BotNotifier()
    sleeper = sleep or (lambda _s: None)

    due = _due_subscriptions(session, now)
    expiring = _expiring_subscriptions(session, now, reminder_days)

    sent = failed = skipped = 0

    def deliver(chat_id: int | str, text: str) -> None:
        nonlocal sent, failed, skipped
        if not notifier.enabled:
            skipped += 1
            return
        result = notifier.send(chat_id, text)
        if result.ok:
            sent += 1
            sleeper(SEND_INTERVAL_SECONDS)
        else:
            failed += 1

    for sub, user in due:
        if user.is_banned:
            continue
        deliver(user.telegram_id, expiry_notice_text(user, sub, user.currency or currency))

    for sub, user in expiring:
        if user.is_banned:
            continue
        days_left = max(0, (sub.expires_at - now).days)
        deliver(
            user.telegram_id,
            renewal_reminder_text(user, sub, days_left, user.currency or currency),
        )

    expired = expire_stale_subscriptions(session, now)

    report = MaintenanceReport(
        expired=expired,
        reminded=len(expiring),
        sent=sent,
        failed=failed,
        skipped=skipped,
        digest_sent=False,
    )

    target = owner_chat if owner_chat is not None else owner_chat_id()
    if target is not None and notifier.enabled:
        digest = daily_digest_text(session, report, now=now, currency=currency)
        report = replace(report, digest_sent=notifier.send(target, digest).ok)

    return report


DEFAULT_STATE_FILE = "logs/lifecycle_last_run.txt"


def run_daily_if_due(
    session: Session,
    *,
    now: datetime | None = None,
    state_path: str | Path | None = None,
    **kwargs,
) -> MaintenanceReport | None:
    """
    Runs the job at most once per UTC calendar day.

    The scheduler ticks every few hours; without this gate every tick would
    re-send the same reminders and burn the bot's rate limit.
    """
    now = now or datetime.utcnow()
    path = Path(state_path or DEFAULT_STATE_FILE)
    today = now.strftime("%Y-%m-%d")

    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == today:
            return None
    except OSError:
        pass

    report = run_daily_maintenance(session, now=now, **kwargs)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(today, encoding="utf-8")
    except OSError as e:  # pragma: no cover - read-only filesystem
        print(f"[lifecycle] could not write state file {path}: {e}", flush=True)

    return report
