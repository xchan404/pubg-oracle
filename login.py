import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")

if not API_ID or not API_HASH:
    print("❌ خطأ: لم يتم العثور على API_ID أو API_HASH في ملف .env")
    exit(1)

print("🔑 جاري تسجيل الدخول لبرمجة القناص (UserBot)...")
print(f"📌 API_ID: {API_ID}")

# إنشاء الجلسة
client = TelegramClient('sniper_session', int(API_ID), API_HASH)

async def main():
    # client.start() سيطلب منك إدخال رقم هاتفك والكود إذا كانت هذه أول مرة
    await client.start()
    print("\n✅ تم تسجيل الدخول بنجاح! تم حفظ الجلسة في ملف sniper_session.session")
    print("🎯 يمكنك الآن تشغيل البوت الأساسي ليقوم بالقنص عبر حسابك.")
    
if __name__ == "__main__":
    asyncio.run(main())
