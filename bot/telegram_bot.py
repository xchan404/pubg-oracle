import asyncio
import io
import os
import re
import sys

from aiohttp import web
from dotenv import load_dotenv
from sqlalchemy import select
from telethon import Button, TelegramClient, events

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'buffer') and 'pytest' not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from bot import paywall
from database.ads import initialize as init_ads_db
from database.ads import save_ad
from database.db import SessionLocal
from database.feedback import save_feedback
from database.models import Payment, User
from database.users import get_or_create
from ml.active_learning import select_review_queue
from ml.predict import EnsemblePricer
from parser.regex_parser import parse_account_data
from services.catalog import OFFERS
from services.entitlements import get_entitlement
from services.payments import approve_payment, reject_payment
from services.usage import credit_balance

_ = (save_feedback, select_review_queue)  # used in handlers defined below

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')
MIN_PROFIT = int(os.getenv('MIN_PROFIT_THRESHOLD', 300))
TARGET_CHATS_ENV = os.getenv('TARGET_CHATS', '')

if not API_ID or not API_HASH:
    print("❌ خطأ: يرجى وضع API_ID و API_HASH في ملف .env")
    sys.exit(1)

if not BOT_TOKEN or not MY_CHAT_ID:
    print("❌ خطأ: يرجى وضع BOT_TOKEN و MY_CHAT_ID في ملف .env")
    sys.exit(1)

MY_CHAT_ID = int(MY_CHAT_ID) if MY_CHAT_ID.lstrip('-').isdigit() else MY_CHAT_ID

# تجهيز قائمة الجروبات المستهدفة (إذا وجدت)
target_chats = []
if TARGET_CHATS_ENV:
    for chat in TARGET_CHATS_ENV.split(','):
        chat = chat.strip()
        if chat:
            target_chats.append(int(chat) if chat.lstrip('-').isdigit() else chat)

# تهيئة الموديل
print("⏳ جاري تحميل الذكاء الاصطناعي ومحرك التسعير...")
pricer = EnsemblePricer()
print("✅ محرك التسعير جاهز للاصطياد!")

# الـ UserBot (حسابك الشخصي) - عشان يقرأ الجروبات
client = TelegramClient('pubg_scraper_session', int(API_ID), API_HASH)

# بوت التنبيهات (البوت الخاص بك) - عشان يبعتلك التنبيهات ويرد عليك
bot_client = TelegramClient('bot_sniper_session', int(API_ID), API_HASH)
# ── Phase 3: حالة انتظار "السعر النهائي" بعد الضغط على زر اتباعع بسعر ──
PENDING_PRICE = {}
# ── Week 3: حالة انتظار إثبات الدفع اليدوي (فودافون كاش / إنستاباي) ──
PENDING_PAYMENT = {}


def feedback_buttons(chat_id: int, message_id: int, fingerprint: str = ""):
    """Inline keyboard binding a label to the ORIGINAL ad coordinates."""
    payload = f"{chat_id}|{message_id}|{fingerprint or ''}"
    return [[
        Button.inline("✅ اشتريته", f"buy|{payload}".encode()),
        Button.inline("💰 اتباع بسعر", f"price|{payload}".encode()),
    ], [
        Button.inline("❌ مش صفقة", f"nope|{payload}".encode()),
        Button.inline("🐛 استخراج غلط", f"wrong|{payload}".encode()),
    ]]


LABEL_MAP = {
    "buy": "bought",
    "price": "sold_price",
    "nope": "not_a_deal",
    "wrong": "wrong_parse",
}


def escape_html(text):
    """تهرب الرموز الخاصة اللي ممكن تكسر HTML"""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


from ml.pipeline import pipeline_instance


def price_text(text):
    """يسعر نص الإعلان ويرجع تقرير HTML"""
    parsed = pipeline_instance.process(text)
    asking_price = parsed.get('price_egp')

    res = pricer.predict(parsed, asking_price=asking_price)
    fair_value = res['fair_value_egp']

    adv = res.get('flipping_advice', {})
    rating = adv.get('deal_rating', '❓')

    msg  = "🤖 <b>تقرير التسعير بالذكاء الاصطناعي (محدث)</b>\n\n"
    if asking_price and asking_price > 100:
        profit = adv.get('target_sell_price', 0) - asking_price
        msg += f"💰 <b>المطلوب:</b> {asking_price} ج.م\n"
        msg += f"⚖️ <b>السعر العادل:</b> {fair_value:.0f} ج.م\n"
        msg += f"💵 <b>هدف البيع:</b> {adv.get('target_sell_price', 0):.0f} ج.م\n"
        msg += f"📈 <b>المكسب المتوقع:</b> {profit:.0f} ج.م\n"
        msg += f"🏷️ <b>التقييم:</b> {rating}\n\n"
    else:
        msg += f"⚖️ <b>السعر العادل التقديري:</b> {fair_value:.0f} ج.م\n"
        msg += "⚠️ <i>لم يتم العثور على سعر مطلوب.</i>\n\n"

    # --- التفاصيل الإضافية ---
    msg += f"🎯 <b>دقة التقييم:</b> {escape_html(res.get('confidence', {}).get('label', ''))}\n"
    msg += f"📊 <b>الشريحة:</b> {escape_html(res['segment'])}\n"
    msg += f"✨ <b>البريستيج:</b> {parsed.get('prestige_score', 0)} نقطة\n"
    active_combos = parsed.get("active_combos") or []
    if active_combos:
        msg += f"🔥 <b>كومبوهات:</b> {', '.join(active_combos)}\n"

    msg += "\n📂 <b>ملخص الحساب المستخرج:</b>\n"
    msg += f"🔸 <b>المستوى:</b> {parsed.get('account_level') or 'غير معروف'}\n"
    msg += f"🔸 <b>الميثك:</b> {parsed.get('mythics_count') or 0}\n"
    msg += f"🔸 <b>أسلحة التطوير:</b> {parsed.get('guns_count') or 0}\n"
    if parsed.get('cars_mythic') and parsed['cars_mythic'] > 0:
        msg += f"🏎️ <b>السيارات الميثيك:</b> {parsed['cars_mythic']}\n"

    if parsed.get('m4_type'):
        max_str = '(ماكس)' if parsed.get('m4_is_max') else f"(لفل {parsed.get('m4_level')})"
        msg += f"🔫 <b>امفور 1:</b> {parsed.get('m4_type')} {max_str}\n"
    if parsed.get('m4_2_type'):
        max_str2 = '(ماكس)' if parsed.get('m4_2_is_max') else f"(لفل {parsed.get('m4_2_level')})"
        msg += f"🔫 <b>امفور 2:</b> {parsed.get('m4_2_type')} {max_str2}\n"
    if parsed.get('m4_3_type'):
        max_str3 = '(ماكس)' if parsed.get('m4_3_is_max') else f"(لفل {parsed.get('m4_3_level')})"
        msg += f"🔫 <b>امفور 3:</b> {parsed.get('m4_3_type')} {max_str3}\n"

    rare_found = []
    if parsed.get('has_mummy_helmet'): rare_found.append('خوذة مومياء')
    elif parsed.get('has_mummy'): rare_found.append('مومياء')
    if parsed.get('has_joker_fox_locked'): rare_found.append('جوكر فوكس مقفول')
    elif parsed.get('has_joker_fox'): rare_found.append('جوكر فوكس')
    if parsed.get('has_conqueror'): rare_found.append('كونكر')
    if parsed.get('has_face_girl'): rare_found.append('فيس بنت')
    if parsed.get('has_xsuit'): rare_found.append('بدلة إكس')
    if parsed.get('has_car_mclaren'): rare_found.append('مكلارين')
    if parsed.get('has_car_porsche'): rare_found.append('بورش')
    if parsed.get('has_car_dodge'): rare_found.append('دودج')
    if parsed.get('has_lobby_mythic'): rare_found.append('لوبي ميثك')

    # Extra Ultra Rares
    if parsed.get('has_soap_double'): rare_found.append('دبل صابونة')
    elif parsed.get('has_soap_blue'): rare_found.append('صابونة زرقاء')
    elif parsed.get('has_soap_black'): rare_found.append('صابونة سوداء')
    elif parsed.get('has_soap_rare'): rare_found.append('صابونة نادرة')

    if parsed.get('has_scarf_tiger'): rare_found.append('وشاح النمر')
    if parsed.get('has_hair_qarnain'): rare_found.append('شعر قرنين')
    if parsed.get('has_hair_kaboria'): rare_found.append('شعر كابوريا')
    if parsed.get('has_hair_yellow'): rare_found.append('شعر أصفر')

    if parsed.get('has_plane_frame'): rare_found.append('إطار طيارة')
    if parsed.get('has_re2_frame'): rare_found.append('إطار RE2')
    if parsed.get('has_conqueror_frame'): rare_found.append('إطار كونكر')

    if rare_found:
        msg += f"💎 <b>النوادر:</b> {', '.join(rare_found)}\n"

    return msg


def format_deal_message(res, original_text, chat_title, msg_link, parsed=None):
    adv = res.get('flipping_advice', {})
    rating = adv.get('deal_rating', '❓')

    fair_value = res['fair_value_egp']
    profit = adv.get('target_sell_price', 0) - adv.get('asking_price', 0)

    msg = "🎯 <b>صيدة جديدة من الجروبات!</b> 🎯\n"
    msg += f"📍 <b>الجروب:</b> {escape_html(chat_title)}\n"
    msg += f"🔗 <b>رابط الرسالة:</b> {msg_link}\n\n"

    msg += f"💰 <b>المطلوب:</b> {adv.get('asking_price')} ج.م\n"
    msg += f"⚖️ <b>السعر العادل:</b> {fair_value:.0f} ج.م\n"
    msg += f"💵 <b>هدف البيع:</b> {adv.get('target_sell_price', 0):.0f} ج.م\n"
    msg += f"📈 <b>المكسب المتوقع:</b> {profit:.0f} ج.م\n"
    msg += f"🏷️ <b>التقييم:</b> {rating}\n\n"

    msg += f"🎯 <b>الثقة:</b> {escape_html(res.get('confidence', {}).get('label', ''))}\n"
    msg += f"📊 <b>الشريحة:</b> {escape_html(res['segment'])}\n"

    active_combos = (parsed or {}).get("active_combos") or []
    if active_combos:
        msg += f"🔥 <b>كومبوهات:</b> {', '.join(active_combos)}\n"

    if parsed:
        msg += "\n📂 <b>مستخرجات سريعة:</b>\n"
        msg += f"🔸 المستوى: {parsed.get('account_level') or '?'} | الميثك: {parsed.get('mythics_count') or 0} | الأسلحة: {parsed.get('guns_count') or 0}\n"
        if parsed.get('m4_type'):
            max_str = '(ماكس)' if parsed.get('m4_is_max') else f"(L{parsed.get('m4_level')})"
            msg += f"🔫 امفور: {parsed.get('m4_type')} {max_str}"
            if parsed.get('m4_2_type'):
                max_str2 = '(ماكس)' if parsed.get('m4_2_is_max') else f"(L{parsed.get('m4_2_level')})"
                msg += f" | {parsed.get('m4_2_type')} {max_str2}"
            if parsed.get('m4_3_type'):
                max_str3 = '(ماكس)' if parsed.get('m4_3_is_max') else f"(L{parsed.get('m4_3_level')})"
                msg += f" | {parsed.get('m4_3_type')} {max_str3}"
            msg += "\n"

        rare_found = []
        if parsed.get('has_mummy_helmet'): rare_found.append('خوذة مومياء')
        elif parsed.get('has_mummy'): rare_found.append('مومياء')
        if parsed.get('has_joker_fox_locked'): rare_found.append('جوكر فوكس مقفول')
        elif parsed.get('has_joker_fox'): rare_found.append('جوكر فوكس')
        if parsed.get('has_conqueror'): rare_found.append('كونكر')
        if parsed.get('has_face_girl'): rare_found.append('فيس بنت')
        if parsed.get('has_xsuit'): rare_found.append('بدلة إكس')
        if parsed.get('has_car_mclaren'): rare_found.append('مكلارين')
        if parsed.get('has_car_porsche'): rare_found.append('بورش')
        if parsed.get('has_car_dodge'): rare_found.append('دودج')
        if parsed.get('has_lobby_mythic'): rare_found.append('لوبي ميثك')
        if parsed.get('has_soap_double'): rare_found.append('دبل صابونة')
        elif parsed.get('has_soap_blue'): rare_found.append('صابونة زرقاء')
        elif parsed.get('has_soap_black'): rare_found.append('صابونة سوداء')
        elif parsed.get('has_soap_rare'): rare_found.append('صابونة نادرة')
        if parsed.get('has_scarf_tiger'): rare_found.append('وشاح النمر')
        if parsed.get('has_hair_qarnain'): rare_found.append('شعر قرنين')
        if parsed.get('has_hair_kaboria'): rare_found.append('شعر كابوريا')
        if parsed.get('has_hair_yellow'): rare_found.append('شعر أصفر')
        if parsed.get('has_plane_frame'): rare_found.append('إطار طيارة')
        if parsed.get('has_re2_frame'): rare_found.append('إطار RE2')
        if parsed.get('has_conqueror_frame'): rare_found.append('إطار كونكر')

        if rare_found:
            msg += f"💎 النوادر: {', '.join(rare_found)}\n"

    msg += f"\n📝 <b>الإعلان الأصلي:</b>\n<pre>{escape_html(original_text[:400])}</pre>"

    return msg


# ============================================================
# Bot Handler - عشان البوت يرد على رسايلك
# ============================================================
async def _sender_info(event):
    """Returns (username, first_name) without failing on privacy settings."""
    try:
        sender = await event.get_sender()
    except Exception:
        return None, None
    return getattr(sender, 'username', None), getattr(sender, 'first_name', None)


def _is_admin(event) -> bool:
    return str(event.sender_id) == str(MY_CHAT_ID)


async def _notify_admin_payment(
    payment_id: int,
    telegram_id: int,
    username,
    offer_title: str,
    amount: float,
    currency: str,
    proof: str | None,
) -> None:
    """Sends the owner a review card with approve/reject buttons."""
    try:
        await bot_client.send_message(
            MY_CHAT_ID,
            paywall.payment_request_text(
                payment_id, telegram_id, username, offer_title, amount, currency, proof
            ),
            parse_mode='html',
            buttons=[[
                Button.inline("✅ تفعيل", f"payok|{payment_id}".encode()),
                Button.inline("❌ رفض", f"payno|{payment_id}".encode()),
            ]],
        )
    except Exception as e:
        print(f"[Payments] تعذر إشعار المالك: {e}")


async def _handle_proof_media(event, username, first_name) -> None:
    """Screenshots/documents as payment proof — the bot explicitly asks for them."""
    pending_offer = PENDING_PAYMENT.get(event.sender_id)
    if not pending_offer or not (event.photo or event.document):
        return

    PENDING_PAYMENT.pop(event.sender_id, None)
    with SessionLocal() as session:
        user = get_or_create(
            session, event.sender_id, username=username, first_name=first_name
        )
        payment, offer, amount = paywall.create_wallet_intent(
            session, user, pending_offer, proof_note="screenshot"
        )
        payment_id, currency = payment.id, payment.currency
        offer_title = offer.title_ar
        telegram_id, uname = user.telegram_id, user.username

    try:
        await bot_client.forward_messages(MY_CHAT_ID, event.message)
    except Exception as e:
        print(f"[Payments] تعذر تحويل الإثبات: {e}")

    await _notify_admin_payment(
        payment_id, telegram_id, uname, offer_title, amount, currency, "سكرين شوت"
    )
    await event.reply(
        f"✅ تم استلام إثبات <b>{escape_html(offer_title)}</b>\n"
        f"المبلغ: <b>{amount:,.0f} {escape_html(currency)}</b>\n"
        f"رقم الطلب: <b>#{payment_id}</b>\n\n"
        "هيتم التفعيل بعد المراجعة، وهتوصلك رسالة هنا أول ما يتم.",
        parse_mode='html',
    )


@bot_client.on(events.NewMessage())
async def bot_handler(event):
    """يراقب الرسايل اللي بتبعتها للبوت ويرد عليها بالتسعير"""
    if not event.is_private:
        return

    text = event.text
    username, first_name = await _sender_info(event)

    if not text:
        await _handle_proof_media(event, username, first_name)
        return

    stripped = text.strip()
    command = stripped.split()[0].lower() if stripped else ""

    # ── /start و /help ─────────────────────────────
    if command in ('/start', '/help'):
        with SessionLocal() as session:
            user, applied = paywall.start_user(
                session, event.sender_id,
                username=username, first_name=first_name, payload=stripped,
            )
            name = user.first_name
        extra = f"\n\n✅ تم ربطك بشريك: <code>{escape_html(applied)}</code>" if applied else ""
        await event.reply(paywall.welcome_text(name) + extra, parse_mode='html')
        return

    # ── /plans ─────────────────────────────────────
    if command == '/plans':
        with SessionLocal() as session:
            user = get_or_create(session, event.sender_id, username=username, first_name=first_name)
            currency = user.currency
        await event.reply(paywall.plans_text(currency), parse_mode='html')
        return

    # ── /me ────────────────────────────────────────
    if command in ('/me', '/account'):
        with SessionLocal() as session:
            user = get_or_create(session, event.sender_id, username=username, first_name=first_name)
            summary = paywall.user_summary_text(session, user)
        await event.reply(summary, parse_mode='html')
        return

    # ── /country eg|sa|ae ──────────────────────────
    if command == '/country':
        currency = paywall.country_command(stripped)
        if currency is None:
            await event.reply(
                "استخدم: <code>/country eg</code> أو <code>sa</code> أو <code>ae</code>",
                parse_mode='html',
            )
            return
        with SessionLocal() as session:
            user = get_or_create(session, event.sender_id, username=username, first_name=first_name)
            paywall.set_country(session, user, stripped.split()[1])
        await event.reply(f"✅ تم ضبط العملة على <b>{currency}</b>", parse_mode='html')
        return

    # ── /pay <offer> ───────────────────────────────
    if command == '/pay':
        parts = stripped.split()
        offer_code = parts[1].lower() if len(parts) > 1 else ""
        if offer_code not in OFFERS:
            with SessionLocal() as session:
                user = get_or_create(session, event.sender_id, username=username, first_name=first_name)
                currency = user.currency
            await event.reply(paywall.plans_text(currency), parse_mode='html')
            return
        PENDING_PAYMENT[event.sender_id] = offer_code
        with SessionLocal() as session:
            user = get_or_create(session, event.sender_id, username=username, first_name=first_name)
            currency = user.currency
        await event.reply(
            paywall.payment_instructions_text(offer_code, currency), parse_mode='html'
        )
        return

    # ── /review (admin only) ───────────────────────
    if command == '/review':
        if not _is_admin(event):
            await event.reply("⛔ الأمر ده للمالك فقط.", parse_mode='html')
            return
        await event.reply("⏳ جاري تجهيز قائمة المراجعة...")
        try:
            items = select_review_queue(limit=5)
        except Exception as e:
            await event.reply(f"⚠️ خطأ في قائمة المراجعة: {escape_html(str(e))}", parse_mode='html')
            return
        if not items:
            await event.reply("👌 مفيش إعلانات حديثة محتاجة مراجعة.")
            return
        lines = ["🔍 <b>أقل الإعلانات ثقة — علّم عليها من تنبيهات الصيد:</b>\n"]
        for i, it in enumerate(items, 1):
            asked = it['asked_price'] if it['asked_price'] is not None else '؟'
            lines.append(
                f"<b>{i}.</b> ثقة <b>{it['confidence_pct']}%</b> | "
                f"مطلوب: {asked} | عادل: {it['fair_value']}\n"
                f"<pre>{escape_html(it['excerpt'])}</pre>"
            )
        await event.reply("\n".join(lines), parse_mode='html')
        return

    # ── /payments (admin only) ─────────────────────
    if command == '/payments':
        if not _is_admin(event):
            await event.reply("⛔ الأمر ده للمالك فقط.", parse_mode='html')
            return
        with SessionLocal() as session:
            rows = session.execute(
                select(Payment, User)
                .join(User, User.id == Payment.user_id)
                .where(Payment.status == 'pending')
                .order_by(Payment.created_at.asc())
                .limit(10)
            ).all()
            cards = [
                (
                    p.id, u.telegram_id, u.username,
                    (OFFERS[p.offer_code].title_ar if p.offer_code in OFFERS else (p.offer_code or p.provider)),
                    p.amount, p.currency, p.proof_note,
                )
                for p, u in rows
            ]

        if not cards:
            await event.reply("👌 مفيش مدفوعات معلّقة.")
            return

        for pid, tid, uname, title, amount, currency, proof in cards:
            await event.reply(
                paywall.payment_request_text(pid, tid, uname, title, amount, currency, proof),
                parse_mode='html',
                buttons=[[
                    Button.inline("✅ تفعيل", f"payok|{pid}".encode()),
                    Button.inline("❌ رفض", f"payno|{pid}".encode()),
                ]],
            )
        return

    # ── إثبات دفع يدوي (فودافون كاش / إنستاباي) ─────
    pending_offer = PENDING_PAYMENT.pop(event.sender_id, None)
    if pending_offer:
        if command.startswith('/'):
            PENDING_PAYMENT[event.sender_id] = pending_offer
        else:
            with SessionLocal() as session:
                user = get_or_create(session, event.sender_id, username=username, first_name=first_name)
                payment, offer, amount = paywall.create_wallet_intent(
                    session, user, pending_offer, proof_note=stripped[:500]
                )
                payment_id, currency = payment.id, payment.currency
                offer_title = offer.title_ar
                telegram_id, uname = user.telegram_id, user.username
            await _notify_admin_payment(
                payment_id, telegram_id, uname, offer_title, amount, currency, stripped[:200]
            )
            await event.reply(
                f"✅ تم استلام طلب <b>{escape_html(offer_title)}</b>\n"
                f"المبلغ: <b>{amount:,.0f} {escape_html(currency)}</b>\n"
                f"رقم الطلب: <b>#{payment_id}</b>\n\n"
                "هيتم التفعيل بعد المراجعة، وهتوصلك رسالة هنا أول ما يتم.",
                parse_mode='html',
            )
            return

    # Phase 3: هل المستخدم بيرد بسعر البيع الفعلي بعد زر اتباع بسعر؟
    if await handle_pending_price(event, text):
        return

    # ── بوابة الاشتراك: free = 3 استعلامات / 24 ساعة ──
    if not _is_admin(event):
        with SessionLocal() as session:
            access = paywall.check_access(
                session, event.sender_id, username=username, first_name=first_name
            )
            if not access.allowed:
                credits = credit_balance(session, access.user.id)
                currency = access.user.currency
                await event.reply(
                    paywall.quota_exceeded_text(currency, credits), parse_mode='html'
                )
                return

    print(f"[Bot] رسالة واردة للتسعير: {text[:40]}...")
    try:
        reply_msg = await event.reply("⏳ جاري تسعير الأكونت...")
        report = price_text(text)
        await reply_msg.edit(report, parse_mode='html')
        print("[Bot] تم الرد بالتسعير بنجاح!")
    except Exception as e:
        await event.reply(f"⚠️ حصل خطأ أثناء التسعير: {escape_html(str(e))}", parse_mode='html')
        print(f"[Bot] خطأ في التسعير: {e}")


# ============================================================
# Sniper Handler - مراقبة الجروبات بحسابك الشخصي
# ============================================================
SALE_KEYWORDS = [r'للبيع', r'اكونت', r'حساب', r'متوفر', r'السعر']

def is_account_post(text):
    text = str(text)
    return any(re.search(kw, text, re.IGNORECASE) for kw in SALE_KEYWORDS)


@client.on(events.NewMessage(chats=target_chats if target_chats else None))
async def sniper_handler(event):
    if not event.text:
        return

    text = event.text

    if text.startswith('🎯') or text.startswith('🤖') or text.startswith('⏳'):
        return

    if not is_account_post(text):
        return

    print(f"\n👀 [فحص] تم رصد رسالة محتملة: {text[:40]}...")

    try:
        parsed = parse_account_data(text, text)
        asking_price = parsed.get('price_egp')

        if not asking_price or asking_price < 100:
            print("❌ [تجاهل] لم يتم العثور على سعر واضح في الإعلان.")
            return

        res = pricer.predict(text, asking_price=asking_price)
        fair_value = res.get('fair_value_egp', 0)
        segment = res.get('segment', 'Unknown')

        profit = 0
        if asking_price and fair_value > 0:
            profit = fair_value - asking_price

        # حفظ الإعلان في قاعدة البيانات
        is_new = save_ad(
            chat_id=event.chat_id,
            message_id=event.id,
            raw_text=text,
            asked_price=asking_price,
            fair_value=fair_value,
            profit=profit,
            segment=segment,
            parsed_data=parsed
        )

        if not is_new:
            return  # الإعلان مكرر وتم حفظه مسبقاً

        deal_rating = res.get('flipping_advice', {}).get('deal_rating', '')
        if profit >= MIN_PROFIT or '🔥🔥' in deal_rating:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'محادثة خاصة')

            chat_id_str = str(chat.id)
            if getattr(chat, 'username', None):
                msg_link = f"https://t.me/{chat.username}/{event.id}"
            elif chat_id_str.startswith('-100'):
                msg_link = f"https://t.me/c/{chat_id_str[4:]}/{event.id}"
            else:
                msg_link = f"https://t.me/c/{chat_id_str}/{event.id}"

            report = format_deal_message(res, text, chat_title, msg_link, parsed=parsed)
            print(f"🚀 [صيدة!] المطلوب: {asking_price} | العادل: {fair_value:.0f} | المكسب: {profit:.0f} ج.م")

            await bot_client.send_message(
                MY_CHAT_ID,
                report,
                parse_mode='html',
                buttons=feedback_buttons(event.chat_id, event.id,
                                         str(parsed.get('account_fingerprint', ''))),
            )
            print("✅ تم إرسال التنبيه عبر البوت بنجاح!")
            push_deal_to_dashboard(res, chat_title, msg_link, asking_price)
        else:
            print(f"⚠️ [مكسب ضعيف] {profit} ج.م أقل من الحد ({MIN_PROFIT} ج.م) أو السعر غير مغري.")

    except Exception as e:
        print(f"⚠️ خطأ في معالجة رسالة السنايبر: {e}")


# ============================================================
# Phase 4 — Live Dashboard Feed (fire-and-forget push to API)
# ============================================================
def push_deal_to_dashboard(res, chat_title, msg_link, asking_price):
    """POSTs the deal to the API hub for WebSocket dashboards. Never raises."""
    import json as _json

    async def _post():
        import aiohttp
        base = os.getenv('API_URL', 'http://127.0.0.1:8000').rstrip('/')
        headers = {}
        token = os.getenv('INTERNAL_TOKEN')
        if token:
            headers['X-Internal-Token'] = token
        adv = res.get('flipping_advice') or {}
        payload = {
            'chat_title': chat_title,
            'message_link': msg_link,
            'asked_price': asking_price,
            'fair_value': res.get('fair_value_egp', 0),
            'profit': adv.get('profit_if_bought_at_asking'),
            'segment': res.get('segment', ''),
            'confidence_label': res.get('confidence', {}).get('label', ''),
            'deal_rating': adv.get('deal_rating', ''),
        }
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await session.post(f'{base}/internal/deal', json=payload, headers=headers)

    def _run():
        try:
            asyncio.ensure_future(_post())
        except RuntimeError:
            # No running loop in this thread context; run synchronously-ish
            try:
                asyncio.run(_post())
            except Exception:
                pass

    try:
        _ = _json  # keep json import local-purpose clear
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_post())
        else:
            _run()
    except Exception as e:
        print(f"[dashboard-push] skipped: {e}")


# ============================================================
# Phase 3 — Feedback Flywheel Handlers
# ============================================================
@bot_client.on(events.CallbackQuery(pattern=rb'^(buy|price|nope|wrong)\|'))
async def feedback_callback(event):
    """Records the human label tapped on an alert's inline buttons."""
    try:
        label_key, payload = event.data.decode().split('|', 1)
        orig_chat_s, orig_msg_s, fingerprint = (payload.split('|') + [''])[:3]
        orig_chat_id, orig_message_id = int(orig_chat_s), int(orig_msg_s)
        label = LABEL_MAP.get(label_key)

        if not label:
            await event.answer('تصنيف غير معروف', alert=True)
            return

        if label == 'sold_price':
            PENDING_PRICE[event.sender_id] = {
                'chat_id': orig_chat_id,
                'message_id': orig_message_id,
                'fingerprint': fingerprint or None,
                'label': 'sold_price',
            }
            await event.answer(
                '💰 اكتب السعر النهائي اللي اتباع بيه (الرقم بس)',
                alert=True,
            )
            return

        saved = save_feedback(
            chat_id=orig_chat_id,
            message_id=orig_message_id,
            label=label,
            fingerprint=fingerprint or None,
        )
        await event.answer(
            '✅ تم تسجيل التقييم' if saved else '⚠️ متسجل قبل كده',
            alert=True,
        )
        if saved:
            print(f"[Feedback] {label} على إعلان {orig_message_id} من {orig_chat_id}")
    except Exception as e:
        print(f"⚠️ [feedback_callback] {e}")
        try:
            await event.answer(f'خطأ: {e}', alert=True)
        except Exception:
            pass


# ── Week 3: اعتماد/رفض الدفع من داخل الشات (للمالك فقط) ──
@bot_client.on(events.CallbackQuery(pattern=rb'^(payok|payno)\|\d+$'))
async def payment_callback(event):
    """Approves or rejects a pending manual payment from the owner's phone."""
    if not _is_admin(event):
        await event.answer('⛔ الأمر ده للمالك فقط', alert=True)
        return

    try:
        action, pid_s = event.data.decode().split('|', 1)
        payment_id = int(pid_s)

        with SessionLocal() as session:
            payment = session.get(Payment, payment_id)
            if payment is None:
                await event.answer('❌ الطلب غير موجود', alert=True)
                return
            if payment.status != 'pending':
                await event.answer(f'ℹ️ الطلب {payment.status} بالفعل', alert=True)
                return

            user = session.get(User, payment.user_id)
            if user is None:
                await event.answer('❌ المستخدم غير موجود', alert=True)
                return

            telegram_id = user.telegram_id
            currency = user.currency
            if action == 'payok':
                approve_payment(session, payment, reviewed_by='owner')
                ent = get_entitlement(session, user)
                credits = credit_balance(session, user.id)
                user_text = paywall.activation_text(
                    ent.plan, ent.expires_at, credits, currency
                )
                owner_text = (
                    f"✅ <b>تم تفعيل الطلب #{payment_id}</b>\n"
                    f"الخطة: {ent.plan}\n"
                    f"المبلغ: {payment.amount:,.0f} {payment.currency}"
                )
            else:
                reject_payment(
                    session, payment, reviewed_by='owner', reason='rejected in chat'
                )
                user_text = (
                    "❌ <b>لم نقدر تأكيد التحويل</b>\n\n"
                    "لو حوّلت فعلًا: ابعت رقم العملية + آخر 4 أرقام من المحفظة وهنراجع تاني.\n"
                    "أو اكتب /plans لاختيار طريقة دفع تانية."
                )
                owner_text = f"❌ <b>تم رفض الطلب #{payment_id}</b>"

        try:
            await bot_client.send_message(telegram_id, user_text, parse_mode='html')
        except Exception as e:
            print(f"[Payments] تعذر إبلاغ المستخدم {telegram_id}: {e}")

        await event.answer('تم ✅')
        try:
            await event.edit(owner_text, parse_mode='html')
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️ [payment_callback] {e}")
        try:
            await event.answer(f'خطأ: {e}', alert=True)
        except Exception:
            pass


async def handle_pending_price(event, text):
    """Consumes the actual-sale-price reply when one is pending. Returns True if handled."""
    pending = PENDING_PRICE.pop(event.sender_id, None)
    if not pending:
        return False

    num_match = re.search(r'\d[\d,\.]*', text.replace('ج', '').replace('م', ''))
    if not num_match:
        await event.reply("❌ مش فهم السعر. ابعت الرقم بس (مثال: 4500)", parse_mode='html')
        return True

    try:
        price = float(num_match.group().replace(',', ''))
    except ValueError:
        await event.reply("❌ صيغة السعر غلط. حاول تاني.")
        return True

    saved = save_feedback(
        chat_id=pending['chat_id'],
        message_id=pending['message_id'],
        label='sold_price',
        value_egp=price,
        fingerprint=pending.get('fingerprint'),
    )
    await event.reply(
        f"✅ تم تسجيل سعر البيع الفعلي: <b>{price:,.0f} ج.م</b>\n"
        + ("هتتستخدم في تدريب الموديل تلقائياً 🎯" if saved else "(متسجل قبل كده)")
        , parse_mode='html'
    )
    print(f"[Feedback] sold_price={price:.0f} على إعلان {pending['message_id']}")
    return True



# ============================================================
# Dummy Web Server (For Render Deployment)
# ============================================================
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"[+] Dummy Web Server is listening on port {port} 🌐")

async def main():
    print("\n[+] يتم الآن الاتصال بحساب تليجرام وحساب البوت...")

    # تهيئة قاعدة البيانات الموحدة + ترحيل بيانات sniper.db القديمة إن وجدت
    init_ads_db()

    # بدء كلا الحسابين
    await start_web_server()
    await client.start()
    await bot_client.start(bot_token=BOT_TOKEN)

    print("[+] السنايبر شغال وبيراقب الجروبات... 🦅")
    print(f"[+] التنبيهات والردود عبر البوت (Chat ID: {MY_CHAT_ID})")

    # تشغيل الحدثين (Event Loops) معاً
    await asyncio.gather(
        client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )


if __name__ == '__main__':
    # لتجنب أخطاء الإغلاق المفاجئ في بعض بيئات ويندوز
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
