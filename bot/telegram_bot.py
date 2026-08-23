import os
import sys
import io
import re
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from telethon import TelegramClient, events

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from parser.regex_parser import parse_account_data
from ml.predict import EnsemblePricer
from db.database import save_ad
from parser.aliases import resolve_alias

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


def escape_html(text):
    """تهرب الرموز الخاصة اللي ممكن تكسر HTML"""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


from ml.pipeline import pipeline_instance

def price_text(text):
    """يسعر نص الإعلان ويرجع تقرير HTML"""
    parsed = pipeline_instance.process(text)
    asking_price = parsed.get('price_egp')
    
    res = pricer.predict(parsed, asking_price=asking_price)
    combo_mult = parsed.get("combo_multiplier", 1.0)
    adjusted_fair_value = res['fair_value_egp'] * combo_mult
    
    adv = res.get('flipping_advice', {})
    rating = adv.get('deal_rating', '❓')

    msg  = f"🤖 <b>تقرير التسعير بالذكاء الاصطناعي (محدث)</b>\n\n"
    if asking_price and asking_price > 100:
        profit = (adv.get('target_sell_price') * intel["combo_multiplier"]) - asking_price
        msg += f"💰 <b>المطلوب:</b> {asking_price} ج.م\n"
        msg += f"⚖️ <b>السعر العادل:</b> {adjusted_fair_value:.0f} ج.م\n"
        msg += f"💵 <b>هدف البيع:</b> {adv.get('target_sell_price') * intel['combo_multiplier']:.0f} ج.م\n"
        msg += f"📈 <b>المكسب المتوقع:</b> {profit:.0f} ج.م\n"
        msg += f"🏷️ <b>التقييم:</b> {rating}\n\n"
    else:
        msg += f"⚖️ <b>السعر العادل التقديري:</b> {adjusted_fair_value:.0f} ج.م\n"
        msg += f"⚠️ <i>لم يتم العثور على سعر مطلوب.</i>\n\n"

    # --- التفاصيل الإضافية ---
    msg += f"🎯 <b>دقة التقييم:</b> {escape_html(res.get('confidence', {}).get('label', ''))}\n"
    msg += f"📊 <b>الشريحة:</b> {escape_html(res['segment'])}\n"
    msg += f"✨ <b>البريستيج:</b> {intel['prestige_score']} نقطة\n"
    if intel["active_combos"]:
        msg += f"🔥 <b>كومبوهات:</b> {', '.join(intel['active_combos'])}\n"
    
    msg += f"\n📂 <b>ملخص الحساب المستخرج:</b>\n"
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


def format_deal_message(res, original_text, chat_title, msg_link, intel=None, parsed=None):
    adv = res.get('flipping_advice', {})
    rating = adv.get('deal_rating', '❓')
    
    if intel is None:
        intel = {"combo_multiplier": 1.0, "active_combos": [], "prestige_score": 0}
        
    adjusted_fair_value = res['fair_value_egp'] * intel["combo_multiplier"]
    profit = (adv.get('target_sell_price', 0) * intel["combo_multiplier"]) - adv.get('asking_price', 0)

    msg = f"🎯 <b>صيدة جديدة من الجروبات!</b> 🎯\n"
    msg += f"📍 <b>الجروب:</b> {escape_html(chat_title)}\n"
    msg += f"🔗 <b>رابط الرسالة:</b> {msg_link}\n\n"

    msg += f"💰 <b>المطلوب:</b> {adv.get('asking_price')} ج.م\n"
    msg += f"⚖️ <b>السعر العادل:</b> {adjusted_fair_value:.0f} ج.م\n"
    msg += f"💵 <b>هدف البيع:</b> {adv.get('target_sell_price', 0) * intel['combo_multiplier']:.0f} ج.م\n"
    msg += f"📈 <b>المكسب المتوقع:</b> {profit:.0f} ج.م\n"
    msg += f"🏷️ <b>التقييم:</b> {rating}\n\n"

    msg += f"🎯 <b>الثقة:</b> {escape_html(res.get('confidence', {}).get('label', ''))}\n"
    msg += f"📊 <b>الشريحة:</b> {escape_html(res['segment'])}\n"
    if intel["active_combos"]:
        msg += f"🔥 <b>كومبوهات:</b> {', '.join(intel['active_combos'])}\n"
        
    if parsed:
        msg += f"\n📂 <b>مستخرجات سريعة:</b>\n"
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
@bot_client.on(events.NewMessage())
async def bot_handler(event):
    """يراقب الرسايل اللي بتبعتها للبوت ويرد عليها بالتسعير"""
    if not event.is_private:
        return
        
    text = event.text
    if not text:
        return

    if text.strip() in ['/start', '/help']:
        await event.reply(
            "👋 <b>أهلاً! أنا بوت تسعير أكونتات PUBG</b>\n\n"
            "ابعتلي إعلان الأكونت وأنا هسعرهولك فوراً بالذكاء الاصطناعي! 🤖\n\n"
            "مثال:\n<pre>امفور نمر كيل\nاسكار كيل\nالسعر 2000</pre>",
            parse_mode='html'
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

        res = pricer.predict(text)
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

        if profit >= MIN_PROFIT or '🔥🔥' in res.get('confidence', {}).get('label', ''):
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'محادثة خاصة')

            chat_id_str = str(chat.id)
            if getattr(chat, 'username', None):
                msg_link = f"https://t.me/{chat.username}/{event.id}"
            elif chat_id_str.startswith('-100'):
                msg_link = f"https://t.me/c/{chat_id_str[4:]}/{event.id}"
            else:
                msg_link = f"https://t.me/c/{chat_id_str}/{event.id}"

            report = format_deal_message(res, text, chat_title, msg_link, intel=None, parsed=parsed)
            print(f"🚀 [صيدة!] المطلوب: {asking_price} | العادل: {fair_value:.0f} | المكسب: {profit:.0f} ج.م")

            await bot_client.send_message(MY_CHAT_ID, report, parse_mode='html')
            print("✅ تم إرسال التنبيه عبر البوت بنجاح!")
        else:
            print(f"⚠️ [مكسب ضعيف] {profit} ج.م أقل من الحد ({MIN_PROFIT} ج.م) أو السعر غير مغري.")

    except Exception as e:
        print(f"⚠️ خطأ في معالجة رسالة السنايبر: {e}")



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
