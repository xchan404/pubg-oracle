# -*- coding: utf-8 -*-
"""
إعدادات وتكوين نظام سحب بيانات تلجرام (PUBG Scraper Config)
يقوم هذا الملف بتحميل متغيرات البيئة، وضمان وجود هيكل المجلدات المطلوب،
وتوفير دوال مساعدة لتفسير وتوحيد صيغ روابط القنوات العامة والخاصة.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# قراءة إعدادات تليجرام مع التحقق من وجودها
API_ID_RAW = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "pubg_scraper_session")
DATABASE_URL = os.getenv("DATABASE_URL")

if not API_ID_RAW or not API_HASH:
    raise ValueError(
        "خطأ: يرجى التأكد من ضبط API_ID و API_HASH في ملف .env"
    )

try:
    API_ID = int(API_ID_RAW)
except ValueError:
    raise ValueError("خطأ: يجب أن يكون TELEGRAM_API_ID عبارة عن أرقام فقط.")

API_HASH = str(API_HASH).strip()

# القنوات المستهدفة الافتراضية
DEFAULT_CHANNELS = [
    "https://t.me/+eYSCPNiMAD4zODU8",  # قناة خاصة (رابط دعوة)
    "https://t.me/sa3kgaming1",        # قناة عامة (رابط)
    "https://t.me/COMMANDOSTORE4"       # قناة عامة (رابط)
]

# هيكل المجلدات المطلوب
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SQLITE_DIR = RAW_DATA_DIR / "sqlite"
CSV_DIR = RAW_DATA_DIR / "csv"
JSON_DIR = RAW_DATA_DIR / "json"
LOGS_DIR = BASE_DIR / "logs"

# ملفات التشغيل والبيانات
DB_PATH = SQLITE_DIR / "pubg_accounts.db"
LOG_PATH = LOGS_DIR / "scraper.log"

def ensure_directories():
    """
    تضمن إنشاء جميع المجلدات اللازمة للبيانات والسجلات إذا لم تكن موجودة.
    """
    for directory in [SQLITE_DIR, CSV_DIR, JSON_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# استدعاء تلقائي لتهيئة المجلدات عند استيراد الإعدادات
ensure_directories()

def parse_channel_input(channel_input: str) -> dict:
    """
    تقوم بتحليل رابط القناة وتحديد ما إذا كان عاماً (username) أو خاصاً (invite link).
    
    المعاملات:
        channel_input (str): رابط القناة أو معرفها (مثال: https://t.me/sa3kgaming1 أو https://t.me/+hash)
        
    المخرجات:
        dict: يحتوي على نوع الرابط والقيمة المستخرجة واسم فريد للملفات.
    """
    channel_input = channel_input.strip()
    
    # 1. التحقق من روابط الدعوة للقنوات الخاصة (Private Invite Links)
    # الصيغ الممكنة: https://t.me/+hash أو t.me/+hash أو https://t.me/joinchat/hash
    invite_match = re.search(r"(?:t\.me\/joinchat\/|t\.me\/\+)([a-zA-Z0-9_\-]+)", channel_input)
    if invite_match:
        invite_hash = invite_match.group(1)
        # للملفات، سنستخدم اسم ثابت يعبر عن الهاش لتمييزه
        file_friendly_name = f"private_join_{invite_hash[:8]}"
        return {
            "type": "private",
            "value": invite_hash,
            "display_name": f"Invite_{invite_hash[:8]}",
            "file_name": file_friendly_name,
            "raw_input": channel_input
        }
        
    # 2. التحقق من الروابط العامة (Public Channel Links/Usernames)
    # الصيغ الممكنة: https://t.me/username أو t.me/username أو @username أو username فقط
    username_match = re.search(r"(?:t\.me\/|@)([a-zA-Z0-9_]{4,})", channel_input)
    if username_match:
        username = username_match.group(1)
        return {
            "type": "public",
            "value": username,
            "display_name": username,
            "file_name": username,
            "raw_input": channel_input
        }
        
    # 3. إذا تم إدخال المعرف مباشرة كاسم بدون إضافات
    if re.match(r"^[a-zA-Z0-9_]{4,}$", channel_input):
        return {
            "type": "public",
            "value": channel_input,
            "display_name": channel_input,
            "file_name": channel_input,
            "raw_input": channel_input
        }
        
    # في حال لم يطابق المعايير (افتراض أنه معرف عام)
    clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", channel_input)
    return {
        "type": "unknown",
        "value": channel_input,
        "display_name": clean_name,
        "file_name": clean_name,
        "raw_input": channel_input
    }
