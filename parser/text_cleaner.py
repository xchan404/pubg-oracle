"""
منظف النصوص (Text Cleaner)
يقوم هذا الموديول بتنظيف النصوص الخام (Raw Text) التي يتم جلبها من تليجرام،
عن طريق إزالة الرموز التعبيرية (Emojis)، والزخارف، والروابط، والإبقاء فقط على
النصوص المفيدة للتحليل (العربية، الإنجليزية، الأرقام، والرموز الحسابية).
"""

import hashlib
import re

# Arabic Normalization Dictionary
ARABIC_NORMALIZE = {
    'إ': 'ا', 'أ': 'ا', 'آ': 'ا',
    'ة': 'ه',
    'ى': 'ي',
    'ؤ': 'و',
    'ئ': 'ي',
}

# Arabic Numerals Dictionary
ARABIC_NUMERALS = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}

# Tashkeel (diacritics) + tatweel: invisible to humans, poison for matching
_DIACRITICS_RE = re.compile(r'[\u064B-\u0652\u0670\u0640]')


def strip_diacritics(text: str) -> str:
    """Removes tashkeel/fathatan/dammatan/kasratan/shadda/sukun and tatweel."""
    return _DIACRITICS_RE.sub('', text)


def normalize_arabic(text: str) -> str:
    text = strip_diacritics(text)
    for char, replacement in ARABIC_NORMALIZE.items():
        text = text.replace(char, replacement)
    return text

def convert_arabic_numerals(text: str) -> str:
    for char, replacement in ARABIC_NUMERALS.items():
        text = text.replace(char, replacement)
    return text

def is_spam(text: str) -> bool:
    """
    بناءً على الكلمات المفتاحية لتحديد رسائل الإعلانات أو السخام.
    """
    spam_keywords = ["رشق", "متابعين", "تزويد", "هاك", "هكر", "شحن شدات", "uc مجانا", "شحن مجاني"]
    count = sum(1 for keyword in spam_keywords if keyword in text)
    return count >= 2

def get_text_hash(text: str) -> str:
    """
    لحساب الـ Hash لاكتشاف الإعلانات المكررة (Deduplication).
    """
    clean_base = re.sub(r'[\d\W]+', '', text) # Remove numbers and non-words to hash just the core text
    return hashlib.md5(clean_base.encode('utf-8')).hexdigest()

def clean_text(raw_text: str) -> str:
    """
    تنظيف النص من الإيموجيز والزخارف غير الضرورية.

    المعاملات:
        raw_text (str): النص الخام كما جاء من تليجرام.

    المخرجات:
        str: نص نظيف مهيأ لمعالجة الـ Regex.
    """
    if not raw_text:
        return ""

    # 1. مسح الروابط (HTTP/HTTPS)
    text = re.sub(r'http[s]?://\S+', ' ', raw_text)

    # 2. مسح المعرفات (Usernames) أو روابط التلجرام
    text = re.sub(r'(?:@|t\.me/)\S+', ' ', text)

    # 2.1 التطبيع والتحويل (Arabic Normalization & Numerals)
    text = normalize_arabic(text)
    text = convert_arabic_numerals(text)

    # 3. إزالة الإيموجيز والرموز الغريبة بالإبقاء فقط على:
    # - الحروف العربية (\u0600-\u06FF)
    # - الحروف الإنجليزية والأرقام (\w)
    # - المسافات والأسطر (\s)
    # - بعض علامات الترقيم المهمة للأسعار والخصائص ( $ . , ! / : - ( ) { } [ ] )
    text = re.sub(r'[^\w\s\.\,\$\!\/\:\-\(\)\{\}\[\]\u0600-\u06FF]', ' ', text)

    # 4. تنظيف المسافات الزائدة (تحويل أكثر من مسافة إلى مسافة واحدة)
    # لكن نحافظ على الأسطر الجديدة لأنها تفصل بين الخصائص
    text = re.sub(r'[ \t]+', ' ', text)

    # 5. تنظيف الأسطر الفارغة المتتالية
    text = re.sub(r'\n\s*\n', '\n', text)

    return text.strip()
