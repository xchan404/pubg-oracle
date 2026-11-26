"""
Paywall & onboarding logic for the Telegram bot (Week 3).

Pure Python: no Telethon, no network, no module-level side effects, so it can
be unit-tested directly. `bot/telegram_bot.py` is a thin adapter over this.
"""

import os
from dataclasses import dataclass
from html import escape

from sqlalchemy.orm import Session

from database.models import User
from database.users import apply_referral, get_or_create, set_country_currency
from services.catalog import (
    CURRENCY_BY_COUNTRY,
    DEFAULT_CURRENCY,
    OFFERS,
    get_offer,
    resolve_price,
)
from services.entitlements import get_entitlement
from services.payments import create_payment
from services.usage import checks_used, consume_check, credit_balance

WALLET_NUMBERS = {
    "vodafone_cash": os.getenv("VODAFONE_CASH_NUMBER", "").strip(),
    "instapay": os.getenv("INSTAPAY_HANDLE", "").strip(),
}

SUPPORTED_COUNTRIES = {"eg": "EGP", "sa": "SAR", "ae": "AED"}


def parse_start_payload(text: str) -> str | None:
    """Extracts a partner code from `/start partner_<code>` deep links."""
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if payload.startswith("partner_"):
        payload = payload[len("partner_"):].strip()
    return payload or None


def welcome_text(name: str | None = None) -> str:
    who = f" يا {escape(name)}" if name else ""
    return (
        f"👋 <b>أهلًا{who} في أوراكل أسعار حسابات ببجي</b>\n\n"
        "ابعتلي تفاصيل أي حساب وأنا أقولك سعره العادل في ثواني، "
        "مبني على تحليل آلاف الإعلانات الحقيقية.\n\n"
        "🆓 <b>المجاني:</b> 3 استعلامات كل 24 ساعة\n"
        "⭐ <b>Pro:</b> استعلامات غير محدودة + تنبيهات فورية\n"
        "💼 <b>Business:</b> تصدير و API و5 مقاعد\n\n"
        "/plans — الأسعار والخطط\n"
        "/me — حسابي ورصيدي\n"
        "/help — المساعدة"
    )


def plans_text(currency: str = DEFAULT_CURRENCY) -> str:
    lines = ["💳 <b>خطط الاشتراك</b>", ""]
    for offer in OFFERS.values():
        price = resolve_price(offer, currency)
        lines.append(f"• <b>{offer.title_ar}</b> — {price:,.0f} {currency}")
    lines += [
        "",
        "للشراء: <code>/pay pro_monthly</code> أو <code>/pay credits_5</code>",
        "الدفع: فودافون كاش / إنستاباي / Telegram Stars",
        "",
        "🆓 أو جرّب مجانًا: 3 استعلامات كل 24 ساعة.",
    ]
    return "\n".join(lines)


def payment_instructions_text(
    offer_code: str,
    currency: str = DEFAULT_CURRENCY,
    provider: str = "vodafone_cash",
) -> str:
    offer = get_offer(offer_code)
    if offer is None:
        return "❌ العرض غير معروف. استخدم /plans."

    price = resolve_price(offer, currency)
    number = WALLET_NUMBERS.get(provider) or "—"
    label = "فودافون كاش" if provider == "vodafone_cash" else "إنستاباي"
    return (
        f"🧾 <b>{offer.title_ar}</b>\n"
        f"المبلغ: <b>{price:,.0f} {currency}</b>\n"
        f"التحويل على {label}: <code>{escape(number)}</code>\n\n"
        "بعد التحويل ابعت هنا:\n"
        "• سكرين شوت التحويل، أو\n"
        "• رقم العملية + آخر 4 أرقام من المحفظة\n\n"
        "هيتم التفعيل بعد المراجعة (عادة أقل من ساعة)."
    )


def quota_exceeded_text(
    currency: str = DEFAULT_CURRENCY, credits: int = 0
) -> str:
    if credits > 0:
        return (
            f"⚠️ <b>رصيد الكريدت بتاعك {credits}</b>\n"
            "لو الاستعلام رفض، ابعت /plans لشراء رصيد إضافي."
        )
    return (
        "⛔ <b>خلصت استعلاماتك المجانية</b>\n\n"
        "المجاني 3 استعلامات كل 24 ساعة.\n"
        f"• Pro شهري: <b>{resolve_price(OFFERS['pro_monthly'], currency):,.0f} {currency}</b>\n"
        f"• 5 استعلامات: <b>{resolve_price(OFFERS['credits_5'], currency):,.0f} {currency}</b>\n\n"
        "اكتب /plans للتفاصيل أو /pay pro_monthly للشراء."
    )


def user_summary_text(session: Session, user: User) -> str:
    entitlement = get_entitlement(session, user)
    used = checks_used(session, user.id)
    limit = entitlement.checks_per_day
    limit_text = "غير محدود" if limit is None else str(limit)
    expiry = entitlement.expires_at.strftime("%Y-%m-%d") if entitlement.expires_at else "—"
    return (
        "👤 <b>حسابك</b>\n"
        f"الخطة: <b>{entitlement.plan}</b>\n"
        f"تنتهي: {expiry}\n"
        f"استعلامات آخر 24 ساعة: {used} / {limit_text}\n"
        f"الكريدت: <b>{credit_balance(session, user.id)}</b>\n"
        f"العملة: {user.currency}\n\n"
        "/plans — الترقية"
    )


def activation_text(
    plan: str,
    expires_at=None,
    credits: int = 0,
    currency: str = DEFAULT_CURRENCY,
) -> str:
    """Confirmation shown to the user after an admin approves their payment."""
    if plan == "free":
        lines = ["✅ <b>تم تفعيل رصيدك</b>", ""]
    else:
        expiry = expires_at.strftime("%Y-%m-%d") if expires_at else "—"
        lines = [
            "🎉 <b>تم تفعيل اشتراكك</b>",
            "",
            f"الخطة: <b>{escape(plan)}</b>",
            f"تنتهي: <b>{expiry}</b>",
            "",
            "استعلامات غير محدودة + تنبيهات فورية.",
        ]
    if credits:
        lines += ["", f"🎟️ الكريدت المتاح: <b>{credits}</b>"]
    lines += ["", "ابعت تفاصيل أي حساب وأنا أسعّره فورًا.", "/plans — تفاصيل الخطط"]
    return "\n".join(lines)


def payment_request_text(
    payment_id: int,
    telegram_id: int,
    username: str | None,
    offer_title: str,
    amount: float,
    currency: str,
    proof: str | None = None,
) -> str:
    """The card the owner sees for each new manual payment."""
    handle = f" (@{escape(username)})" if username else ""
    proof_line = f"\nالإثبات: <code>{escape(proof[:200])}</code>" if proof else ""
    return (
        f"🧾 <b>طلب دفع جديد #{payment_id}</b>\n"
        f"المستخدم: <code>{telegram_id}</code>{handle}\n"
        f"العرض: <b>{escape(offer_title)}</b>\n"
        f"المبلغ: <b>{amount:,.0f} {escape(currency)}</b>"
        f"{proof_line}\n\n"
        "راجع التحويل ثم اضغط تفعيل أو رفض."
    )


def country_command(text: str) -> str | None:
    """Parses `/country eg` into a currency code."""
    parts = (text or "").strip().split()
    if len(parts) < 2:
        return None
    return SUPPORTED_COUNTRIES.get(parts[1].lower())


@dataclass(frozen=True)
class AccessResult:
    user: User
    allowed: bool
    plan: str
    remaining: int | None
    used_credit: bool
    reason: str


def start_user(
    session: Session,
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    language: str = "ar",
    payload: str | None = None,
) -> tuple[User, str | None]:
    """Creates/refreshes the user and applies a partner code once."""
    user = get_or_create(
        session, telegram_id,
        username=username, first_name=first_name, language=language,
    )
    code = parse_start_payload(payload or "")
    applied = apply_referral(session, user, code) if code else False
    return user, (code if applied else None)


def check_access(
    session: Session,
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
) -> AccessResult:
    """Creates the user if needed, then consumes one metered check."""
    user = get_or_create(session, telegram_id, username=username, first_name=first_name)
    decision = consume_check(session, user)
    return AccessResult(
        user=user,
        allowed=decision.allowed,
        plan=decision.plan,
        remaining=decision.remaining,
        used_credit=decision.used_credit,
        reason=decision.reason,
    )


def create_wallet_intent(
    session: Session,
    user: User,
    offer_code: str,
    *,
    currency: str | None = None,
    provider: str = "vodafone_cash",
    proof_note: str | None = None,
):
    """Creates a pending payment for a manual wallet transfer."""
    offer = get_offer(offer_code)
    if offer is None:
        raise ValueError(f"Unknown offer: {offer_code}")
    cur = (currency or user.currency or DEFAULT_CURRENCY).upper()
    amount = resolve_price(offer, cur)
    payment = create_payment(
        session,
        user,
        provider=provider,
        amount=amount,
        currency=cur,
        offer_code=offer.code,
        proof_note=proof_note,
    )
    return payment, offer, amount


def set_country(session: Session, user: User, country_code: str) -> str | None:
    """Sets the user's currency from a country code. Returns the currency."""
    currency = SUPPORTED_COUNTRIES.get(country_code.lower())
    if currency is None:
        return None
    set_country_currency(session, user, country_code.upper(), currency)
    return currency


def currency_for_country(country_code: str) -> str:
    return CURRENCY_BY_COUNTRY.get(country_code.upper(), DEFAULT_CURRENCY)
