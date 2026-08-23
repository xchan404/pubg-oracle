# -*- coding: utf-8 -*-
"""
محرك استخراج البيانات (Data Parser) - النسخة الشاملة v3
مبني على تحليل الكلمات الفريدة الفعلية من الداتا المجمعة.
"""

import re
from typing import Optional

def _parse_numeric_value(raw_val: str) -> Optional[float]:
    """Helper to convert strings like '15k', '15.5k', '15 الف', '15,000' to float."""
    if not raw_val:
        return None
    val_str = raw_val.strip().lower()
    
    # Check for 'k' notation (e.g. 15k, 15.5k, 2.5k)
    k_match = re.search(r'(\d[\d,\.]*)\s*k\b', val_str, re.IGNORECASE)
    if k_match:
        try:
            return float(k_match.group(1).replace(',', '')) * 1000.0
        except ValueError:
            pass
            
    # Check for 'الف' or 'ألف' notation
    thousand_match = re.search(r'(\d[\d,\.]*)\s*(?:ألف|الف)\b', val_str, re.IGNORECASE)
    if thousand_match:
        try:
            return float(thousand_match.group(1).replace(',', '')) * 1000.0
        except ValueError:
            pass
            
    # Plain number
    plain_match = re.search(r'(\d[\d,\.]*)', val_str)
    if plain_match:
        try:
            return float(plain_match.group(1).replace(',', ''))
        except ValueError:
            pass
            
    return None

def extract_prices(text: str) -> tuple:
    price_egp, price_usd = None, None

    # 1. Direct USD match ($ prefix or suffix, e.g. $150 or 150$)
    usd_match = re.search(r'(?:\$\s*(\d[\d,\.]*)|(\d[\d,\.]*)\s*\$)', text)
    if usd_match:
        raw_usd = usd_match.group(1) or usd_match.group(2)
        try:
            price_usd = float(raw_usd.replace(',', ''))
        except ValueError:
            pass

    # 2. Look for price after price keywords (السعر, الثمن, price, بكام, etc.)
    price_kw = r'السعر|الثمن|سعره|بسعر|قيمته|بكام|طالب|price'
    m = re.search(
        r'(?:' + price_kw + r')\s*[:=\-\u061f:]*\s*(.{1,120})',
        text, re.IGNORECASE
    )

    search_target = m.group(1) if m else text

    # Try matching EGP explicit pattern: number/shorthand followed by ج/جنيه/EGP/egp
    egp_explicit = re.search(
        r'(\d[\d,\.]*\s*(?:k|الف|ألف)?)\s*(?:ج(?:نيه|ينيه)?|EGP|egp)\b',
        search_target, re.IGNORECASE
    )
    if egp_explicit:
        price_egp = _parse_numeric_value(egp_explicit.group(1))

    # If no explicit EGP unit, look for shorthand k notation (e.g. 15k, 2.5k) in price context
    if not price_egp:
        k_explicit = re.search(r'\b(\d[\d,\.]*\s*k)\b', search_target, re.IGNORECASE)
        if k_explicit:
            price_egp = _parse_numeric_value(k_explicit.group(1))

    # If still no EGP price found and we matched a price keyword line, pick the first valid numeric candidate
    if not price_egp and m:
        candidates = re.findall(r'\b\d[\d,\.]*(?:\s*k|\s*الف|\s*ألف)?\b', search_target, re.IGNORECASE)
        for cand in candidates:
            v = _parse_numeric_value(cand)
            if v and v > 100:
                if price_usd and abs(v - price_usd) < 0.1:
                    continue
                price_egp = v
                break

    # Fallback direct EGP pattern search across the full text
    if not price_egp and not m:
        direct_egp = re.search(
            r'(\d[\d,\.]*\s*(?:k|الف|ألف)?)\s*(?:ج(?:نيه|ينيه)?|EGP|egp)\b',
            text, re.IGNORECASE
        )
        if direct_egp:
            price_egp = _parse_numeric_value(direct_egp.group(1))

    return price_egp, price_usd


def extract_level(text: str) -> Optional[int]:
    m = re.search(
        r'(?:لفل|ليفل|لڤل|المستو[ىي]|مستو[ىي]|lv\.?|level)\s*(?:الحساب)?\s*[:\-]?\s*(\d{1,3})',
        text, re.IGNORECASE
    )
    if m:
        v = int(m.group(1))
        if 1 <= v <= 200:
            return v
    return None


# ─────────────────────────────────────────────────────────────
# 3. عدد الميثكات
# ─────────────────────────────────────────────────────────────

def extract_mythics(text: str) -> Optional[int]:
    # 1. Primary: "ميثك" followed by numbers within 10 non-digit characters
    m1 = re.search(r'(?:ميثيك|ميثك|مثيك|مثك|مسك|mythic)[^\d\n]{0,10}?(\d{1,3})', text, re.IGNORECASE)
    if m1:
        v = int(m1.group(1))
        if 1 <= v <= 999:
            return v

    # 2. Fallback: numbers followed by "ميثك" (not preceded by level)
    m2 = re.search(r'(\d{1,3})\s*(?:ميثيك|ميثك|مثيك|مثك|مسك|mythic)', text, re.IGNORECASE)
    if m2:
        start_idx = max(0, m2.start() - 15)
        prefix = text[start_idx:m2.start()].lower()
        if not re.search(r'(?:لفل|ليفل|لڤل|level|lv)\s*$', prefix):
            v = int(m2.group(1))
            if 1 <= v <= 999:
                return v

    return None


# ─────────────────────────────────────────────────────────────
# 4. عدد أسلحة المختبر
# ─────────────────────────────────────────────────────────────

def extract_guns_count(text: str) -> Optional[int]:
    """استخراج عدد الأسلحة في مختبر التطوير."""
    m = re.search(
        r'(?:مختبر\s*التطوير|المختبر\s*المطور|التطوير|مختبر|اسلح[هة]?\s*التطوير|الا?سلح[هة]?\s*المطور[هة]?|اسلحه\s*بيطور)\s*[\[\]:\-\(\)\s]*(\d{1,3})',
        text, re.IGNORECASE
    )
    if not m:
        m = re.search(r'(\d{1,3})\s*(?:سلاح\s*بيطور|اسلح[هة]?\s*تطوير|اسلح[هة]\s*مطور[هة]?|جن\s*تطوير)', text, re.IGNORECASE)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 200:
            return v
    # Fallback: NUMBER + Arabic abbreviation (e.g. 32س = 32 weapons)
    if not m:
        import re as _re
        m2 = _re.search(
            r'(?:مختبر\s*تطوير|تطوير)\s*(\d{1,3})\s*[سصض]',
            text, _re.IGNORECASE
        )
        if m2:
            v2 = int(m2.group(1))
            if 1 <= v2 <= 200:
                return v2
    return None


# ─────────────────────────────────────────────────────────────
# NEW: تفاصيل الأسلحة الأخرى (AKM, M762, AWM, UZI, UMP)
# ─────────────────────────────────────────────────────────────

def extract_weapons_detail(text: str) -> dict:
    result = {
        'has_akm': False, 'akm_is_max': False,
        'has_m762': False, 'm762_is_max': False,
        'has_awm': False, 'awm_is_max': False,
        'has_uzi': False, 'uzi_is_max': False,
        'has_ump': False, 'ump_is_max': False,
        'has_scar': False, 'scar_is_max': False,
    }
    
    # AKM
    if re.search(r'akm|اكيام|اكي\s*ام|ايه\s*كي|اي\s*كي\s*ام|اي\s*كي', text, re.IGNORECASE):
        result['has_akm'] = True
        if re.search(r'(?:akm|ايه\s*كي|اي\s*كي).{0,20}(?:ماكس|max|شكل\s*نهائي)', text, re.IGNORECASE):
            result['akm_is_max'] = True
                
    # M762 / Beryl
    if re.search(r'm7|m762|ام\s*سفن|بيريل|beryl', text, re.IGNORECASE):
        result['has_m762'] = True
        if re.search(r'(?:m7|m762|ام\s*سفن|بيريل|beryl).{0,20}(?:ماكس|max|شكل\s*نهائي)', text, re.IGNORECASE):
            result['m762_is_max'] = True
            
    # AWM
    if re.search(r'awm|اوم', text, re.IGNORECASE):
        result['has_awm'] = True
        if re.search(r'(?:awm|اوم).{0,20}(?:ماكس|max|شكل\s*نهائي)', text, re.IGNORECASE):
            result['awm_is_max'] = True
            
    # UZI
    if re.search(r'uzi|اوزي', text, re.IGNORECASE):
        result['has_uzi'] = True
        if re.search(r'(?:uzi|اوزي).{0,20}(?:ماكس|max|شكل\s*نهائي)', text, re.IGNORECASE):
            result['uzi_is_max'] = True
            
    # UMP (Rare only: الحوت، بيانو، انفجار، نبض، ثلجي، انوبيس، حاكم/حاصد OR Max/Kill Message)
    ump_rare_pattern = r'(?:ump|يومب[يى]?|يوامب[يى]?|امب|يو\s*ام\s*بي|يو\s*ان\s*بي).{0,25}(?:حوت|بيانو|انفجار|نبض|ثلجي|تلجي|ice|piano|انوبيس|حاكم|حاصد|ماكس|max|كيل|مسج|ضرر)'
    if re.search(ump_rare_pattern, text, re.IGNORECASE):
        result['has_ump'] = True
        if re.search(r'(?:ump|يومب[يى]?|يوامب[يى]?|امب|يو\s*ام\s*بي).{0,20}(?:ماكس|max|شكل\s*نهائي)', text, re.IGNORECASE):
            result['ump_is_max'] = True
            
    # SCAR (Rare only: جوكر، موسيقي، اطياب، يقطين، نيون، قطبيه، غريم، ثلجي/تلجي OR Max/Kill Message)
    scar_rare_pattern = r'(?:scar|سكار|اسكار).{0,25}(?:جوكر|موسيقي|اطياب|يقطين|نيون|قطبي|غريم|تلجي|ثلجي|ماكس|max|كيل|مسج)'
    if re.search(scar_rare_pattern, text, re.IGNORECASE):
        result['has_scar'] = True
        if re.search(r'(?:scar|سكار|اسكار).{0,20}(?:ماكس|max|شكل\s*نهائي)', text, re.IGNORECASE):
            result['scar_is_max'] = True

    return result

# ─────────────────────────────────────────────────────────────
# NEW: لفل المجموعات
# ─────────────────────────────────────────────────────────────

def extract_collection_level(text: str) -> Optional[float]:
    """
    استخراج لفل المجموعات (Collection Level).
    يدعم الأرقام العشرية مثل 76.5 و 83.7
    """
    m = re.search(
        r'(?:كولكشن|(?:لفل|ليفل|مستو[ىي])\s*(?:المجموعات?|المجموع[هة]?))\s*[:\-\(]?\s*([0-9]+(?:[\.,][0-9]+)?)',
        text, re.IGNORECASE
    )
    if m:
        try:
            v = float(m.group(1).replace(',', '.'))
            if 1 <= v <= 120:
                return v
        except ValueError:
            pass
    return None


# ─────────────────────────────────────────────────────────────
# NEW: الرفقاء (Companions)
# ─────────────────────────────────────────────────────────────

def extract_companions(text: str) -> dict:
    # الموميا العادية والصفراء والبيضاء
    has_mummy = 1 if re.search(r'موميا\s*بيض|موميا\s*صفر|موميا', text, re.IGNORECASE) else 0
    has_double_mummy = 1 if re.search(r'موميا.{0,10}موميا|موميتين', text, re.IGNORECASE) else 0

    # خوذة الموميا (Mummy Helmet)
    has_mummy_helmet = 1 if re.search(r'خوذ[هة]\s*(?:الموميا|موميا|مومياء|المومياء|الفرعون|فرعون|الجحيم|راكب\s*الجحيم)', text, re.IGNORECASE) else 0

    # السيارات الميثيك والكونكر
    has_vehicle_dev = 1 if re.search(r'عربي[هة]\s*تطوير|سيار[هة]\s*تطوير|مكلارين\s*تطوير|عربي.*?بتتطور|عربي.*?للتطوير|سيار.*?للتطوير', text, re.IGNORECASE) else 0
    has_conqueror = 1 if re.search(r'كونكر|conqueror', text, re.IGNORECASE) else 0
    
    return {
        'has_falcon': bool(re.search(r'صقر|الصقر|falcon', text, re.IGNORECASE)),
        'has_dog': bool(re.search(r'كلب|الكلب|شيبا|dog|shiba', text, re.IGNORECASE)),
        'has_cat': bool(re.search(r'قط[هة]|القط[هة]|cat', text, re.IGNORECASE)),
        'has_poro': bool(re.search(r'بورو|poro', text, re.IGNORECASE)),
        'has_penguin': bool(re.search(r'بطريق|البطريق|penguin', text, re.IGNORECASE)),
        'has_mummy': has_mummy,
        'has_double_mummy': has_double_mummy,
        'has_mummy_helmet': has_mummy_helmet,
        'has_conqueror': has_conqueror,
        'has_vehicle_dev': has_vehicle_dev,
    }

# ─────────────────────────────────────────────────────────────
# NEW: عدد السيارات الكلي + سيارات الإسقاط الجوي
# ─────────────────────────────────────────────────────────────

def extract_cars_info(text: str) -> dict:
    """
    استخراج:
      - cars_total:  العدد الإجمالي للسيارات
      - cars_mythic: عدد السيارات الميثك
      - has_airdrop_car: هل يوجد سيارة إسقاط جوي
    """
    result = {'cars_total': None, 'cars_mythic': None, 'has_airdrop_car': False}

    # إجمالي السيارات: "10 سيارات" / "11 سياره" / "11 عربيات"
    m = re.search(
        r'(\d{1,2})\s*(?:سيار[هةات]+|عربي[هةات]+|مركب[هةات]+)',
        text, re.IGNORECASE
    )
    if m:
        v = int(m.group(1))
        if 1 <= v <= 50:
            result['cars_total'] = v
    elif re.search(r'\b(?:عربيتين|سيارتين)\b', text, re.IGNORECASE):
        result['cars_total'] = max(result.get('cars_total') or 0, 2)

    # سيارات الميثك: "7 سيارات ميثك" / "سيارات ميثك 5"
    m2 = re.search(
        r'(\d{1,2})\s*(?:سيار[هةات]+|عربي[هةات]+)\s*(?:ميثك|مثيك|mythic)',
        text, re.IGNORECASE
    )
    if not m2:
        m2 = re.search(
            r'(?:سيار[هةات]+|عربي[هةات]+)\s*(?:ميثك|مثيك)\s*(\d{1,2})',
            text, re.IGNORECASE
        )
        
    if m2:
        v2 = int(m2.group(1))
        if 1 <= v2 <= 30:
            result['cars_mythic'] = v2
    elif re.search(r'\b(?:عربيتين|سيارتين)\s*(?:بورش|مكلارين|دودج|دوج)?\s*(?:ميثك|مثيك|mythic)\b', text, re.IGNORECASE):
        result['cars_mythic'] = 2

    # إسقاط جوي / اسقاط
    if re.search(r'(?:سيار[هة]\s*)?(?:إسقاط|اسقاط)\s*(?:جوي|جو)', text, re.IGNORECASE):
        result['has_airdrop_car'] = True

    return result


# ─────────────────────────────────────────────────────────────
# 5. عدد بدلات الإكس
# ─────────────────────────────────────────────────────────────

def extract_xsuits_count(text: str) -> Optional[int]:
    """استخراج عدد بدلات الإكس إن وُجد."""
    # "3 بدلات اكس" أو "بدلات اكس 5"
    m = re.search(r'(\d{1,2})\s*بدلا?[تة]\s*اكس', text, re.IGNORECASE)
    if not m:
        m = re.search(r'بدلا?[تة]\s*اكس\s*[:\-]?\s*(\d{1,2})', text, re.IGNORECASE)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 30:
            return v
    # "بدلة اكس" مفردة → 1
    if re.search(r'بدل[هة]\s*اكس|بدلة\s*x\b|xsuit', text, re.IGNORECASE):
        return 1
    return None


# ─────────────────────────────────────────────────────────────
# 6. نوع الامفور ومستواه
# ─────────────────────────────────────────────────────────────

_M4_TYPES = [
    # الأكثر ندرةً وقيمةً أولاً
    ('snoopy',     r'شنوبي|شينوبي|snoopy'),
    ('rhahal',     r'رحال[هة]?|rhahal|traveler'),
    ('emperor',    r'امبراطور|الامبراطور|emperor'),
    ('aether',     r'اثير|الاثير|الأثير|aether'),
    ('master',     r'المعلم|\bمعلم\b|master'),
    ('silver',     r'الفضية?|فضي[يه]|silver'),
    ('glacier',    r'تلجي|ثلجي|تلاجه|تلاجة|ثلجه|glacier|جلاسير|جليد|الجليد'),
    ('joker',      r'جوكر|الجوكر|joker|بلياتشو|مهرج'),
    ('mummy',      r'موميا|مومياء|mummy|الموميا'),
    ('tiger',      r'نمر|النمر|tiger'),
    ('fire',       r'ناري|fire|\bنار\b|النار|ناريه'),
    ('water',      r'ماي|ماء|water|البحر'),
    ('piranha',    r'سحلي[هةة]|بيرانا|piranha'),
    ('pharaoh',    r'فرعون|pharaoh'),
    ('raven',      r'غراب|raven|\bكرو\b'),
    ('desert',     r'صحراء|desert'),
    ('enakiya',    r'عناق|العناق'),
    ('mermaid',    r'حورية|الحورية|حوري[هة]'),
    ('new',        r'الجديد'),
]

def extract_m4_info(text: str) -> dict:
    result = {'m4_type': None, 'm4_level': None, 'm4_is_max': False, 'm4_count': 0, 'm4_2_type': None, 'm4_2_level': None, 'm4_2_is_max': False}

    m4_pat = r'(?:[اأإآ]م\s*فور|[اأإآ]م\s*4|m4|m416)'
    raw_matches = list(re.finditer(f'{m4_pat}\\b', text, re.IGNORECASE))
    
    # Filter out fake M4 mentions (like "شنطه الامفور", "خوذة الامفور")
    matches = []
    for base_m in raw_matches:
        start_check = max(0, base_m.start() - 15)
        prefix = text[start_check:base_m.start()]
        if not re.search(r'(?:شنط[هة]|خوذ[هة]|رقص[هة]|ميدالي[هة])\s*(?:ال)?\s*$', prefix):
            matches.append(base_m)

    if not matches:
        return result

    level_kw_scores = {'ماكس': 3, 'max': 3, 'كيل': 2, 'kill': 2, 'مسج': 2, 'تلجي': 1, 'glacier': 1, 'ضرر': 1, 'damage': 1}
    parsed_m4s = []

    for base_m in matches:
        ls = text.rfind('\n', 0, base_m.start())
        ls = 0 if ls == -1 else ls + 1
        le = text.find('\n', base_m.end())
        le = len(text) if le == -1 else le
        lw = text[ls:le].lower()
        
        score = sum(v for kw, v in level_kw_scores.items() if kw in lw)
        
        for lv_m in re.finditer(r'(?:لفل|ليفل|لڤل|لڤيل|lv\.?|level|مستو[ىي])\s*[:\-]?\s*(\d{1,2})', lw, re.IGNORECASE):
            v = int(lv_m.group(1))
            if 1 <= v <= 10:
                score += (v * 0.1)
                break
                
        parsed_m4s.append({
            'base': base_m,
            'ls': ls,
            'le': le,
            'score': score
        })

    parsed_m4s.sort(key=lambda x: x['score'], reverse=True)

    tight_types = []
    for t, pat in _M4_TYPES:
        if t in ['mummy', 'joker', 'pharaoh']:
            tight_types.append((t, rf'{m4_pat}\s*(?:{pat})|(?:{pat})\s*{m4_pat}'))
        else:
            tight_types.append((t, pat))

    final_m4s = []
    used_lines = set()
    for m in parsed_m4s:
        line_key = (m['ls'], m['le'])
        if line_key in used_lines:
            continue
            
        start_idx = max(m['ls'], m['base'].start() - 35)
        end_idx = min(m['le'], m['base'].end() + 35)
        win = text[start_idx:end_idx].lower()
        
        m4_type = None
        for t_key, pattern in tight_types:
            if re.search(pattern, win, re.IGNORECASE):
                m4_type = t_key
                break
                
        m4_level = None
        for lv_m in re.finditer(r'(?:لفل|ليفل|لڤل|لڤيل|lv\.?|level|مستو[ىي])\s*[:\-]?\s*(\d{1,2})', win, re.IGNORECASE):
            v = int(lv_m.group(1))
            if 1 <= v <= 10:
                m4_level = v
                break
                
        # Fallback for bare numbers immediately following M4 keywords (e.g. "امفور تلجي 3")
        if not m4_level:
            for bare_m in re.finditer(r'(?:[اأإآ]م\s*فور|[اأإآ]م\s*4|m4|m416|تلجي|glacier|نمر|جوكر|طقم|رحالة|سحلية|ناري|نار|النار|fire)\s*([1-7])\b', win, re.IGNORECASE):
                m4_level = int(bare_m.group(1))
                break

        m4_is_max = False
        if re.search(r'\bماكس\b|مااكس|\bmax\b|ق\s*الماكس|شكل\s*نهائي', win, re.IGNORECASE):
            m4_is_max = True
            m4_level = 7
        elif bool(re.search(r'كيل\s*مسج|مسدج|كيل\b', win, re.IGNORECASE)):
            m4_level = max(m4_level or 0, 4)
        elif bool(re.search(r'شكل\s*متقدم', win, re.IGNORECASE)):
            m4_level = max(m4_level or 0, 2)
        elif bool(re.search(r'اساسي|أساسي', win, re.IGNORECASE)):
            m4_level = max(m4_level or 0, 1)
            
        if m4_type or m4_level:
            final_m4s.append({
                'm4_type': m4_type,
                'm4_level': m4_level,
                'm4_is_max': m4_is_max
            })
            used_lines.add(line_key)

    has_explicit_double = bool(re.search(rf'دبل\s*{m4_pat}|[اأإآ]مفورين|[اأإآ]م\s*فورين|2\s*{m4_pat}', text, re.IGNORECASE))
    has_explicit_triple = bool(re.search(rf'تريبل|تربل|ثلاث|3\s*{m4_pat}', text, re.IGNORECASE))

    if not has_explicit_double and not has_explicit_triple:
        unique_typed = []
        for m in final_m4s:
            if m['m4_type'] is not None:
                if not any(x['m4_type'] == m['m4_type'] for x in unique_typed):
                    unique_typed.append(m)
        if not unique_typed and final_m4s:
            unique_typed = [final_m4s[0]]
        final_m4s = unique_typed

    if final_m4s:
        result['m4_type'] = final_m4s[0]['m4_type']
        result['m4_level'] = final_m4s[0]['m4_level']
        result['m4_is_max'] = final_m4s[0]['m4_is_max']
        
        if has_explicit_triple:
            result['m4_count'] = max(3, len(final_m4s))
        elif has_explicit_double:
            result['m4_count'] = max(2, len(final_m4s))
        else:
            result['m4_count'] = len(final_m4s)
            
        if len(final_m4s) > 1:
            result['m4_2_type'] = final_m4s[1]['m4_type']
            result['m4_2_level'] = final_m4s[1]['m4_level']
            result['m4_2_is_max'] = final_m4s[1]['m4_is_max']
            
        if len(final_m4s) > 2:
            result['m4_3_type'] = final_m4s[2]['m4_type']
            result['m4_3_level'] = final_m4s[2]['m4_level']
            result['m4_3_is_max'] = final_m4s[2]['m4_is_max']

    return result


# ─────────────────────────────────────────────────────────────
# 7. قاموس العناصر النادرة الشامل
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# NEW: إطارات نادرة
# ─────────────────────────────────────────────────────────────

_RARE_FRAMES = {
    # ── كونكر ──
    'frame_conqueror':      r'(?:اطار|إطار|ايطار)\s*(?:كونكر|conqueror)',
    'frame_conqueror_old':  r'\b(?:كونكر)\s*(?:قديم|s9|s10|s11|s12)',
    # ── طيارة ──
    'frame_plane_silver':   r'(?:اطار|إطار|ايطار)\s*(?:طيار[هةا]|الطيار[هة])\s*(?:فضي|الفضي)',
    'frame_plane_gold':     r'(?:اطار|إطار|ايطار)\s*(?:طيار[هةا]|الطيار[هة])\s*(?:ذهبي|الذهبي)',
    'frame_plane':          r'(?:اطار|إطار|ايطار)\s*(?:طيار[هةا]|الطيار[هة])',
    # ── جودزيلا ──
    'frame_jodzilla':       r'(?:اطار|إطار|ايطار)\s*(?:جودزيلا|جوزيلا|godzilla)',
    # ── جوكر ──
    'frame_joker':          r'(?:اطار|إطار|ايطار)\s*(?:جوكر|الجوكر)',
    # ── فرعون ──
    'frame_pharaoh':        r'(?:اطار|إطار|ايطار)\s*(?:فرعون|الفرعون)',
    # ── RE2 / Resident Evil ──
    'frame_re2':            r'(?:اطار|إطار|ايطار)\s*(?:RE2|re2|ER2|R2|resident|ريزنت|ريزدنت|رزدنت)',
    # ── ذهبي / جولد ──
    'frame_gold':           r'(?:اطار|إطار|ايطار)\s*(?:جولد|الجولد|ذهبي)',
    # ── روك ستار ──
    'frame_rock_star':      r'(?:اطار|إطار|ايطار)\s*(?:روك\s*ستار|rock\s*star)',
    # ── القلوب ──
    'frame_hearts':         r'(?:اطار|إطار|ايطار)\s*(?:القلوب|قلوب|hearts)',
    # ── برق / ليتنينج ──
    'frame_lightning':      r'(?:اطار|إطار|ايطار)\s*(?:برق|البرق|lightning)',
    # ── كرو / مترو ──
    'frame_crow':           r'(?:اطار|إطار|ايطار)\s*(?:الكرو|كرو)',
    'frame_metro':          r'(?:اطار|إطار|ايطار)\s*(?:مترو|المترو)',
    # ── عدة إطارات نادرة ──
    'frame_rare_multiple':  r'(?:\d+)\s*(?:اطارات|إطارات|ايطارات)\s*(?:كونكر|نادر)',
}

def extract_frames_info(text: str) -> dict:
    """استخراج الإطارات النادرة وعددها."""
    found_frames = []
    for key, pattern in _RARE_FRAMES.items():
        if re.search(pattern, text, re.IGNORECASE):
            # منع parent إن وُجد child أدق
            if key == 'frame_plane' and (
                'frame_plane_silver' in found_frames or 'frame_plane_gold' in found_frames
            ):
                continue
            if key == 'frame_conqueror' and 'frame_conqueror_old' in found_frames:
                continue
            found_frames.append(key)

    # عدد إطارات الكونكر إن ذُكر
    conq_count = None
    m = re.search(r'(\d{1,2})\s*(?:اطار|إطار|ايطار)\s*(?:كونكر|conqueror)', text, re.IGNORECASE)
    if not m:
        m = re.search(r'(\d{1,2})\s*(?:اطارات|إطارات|ايطارات)\s*(?:كونكر|conqueror)', text, re.IGNORECASE)
    if not m:
        m = re.search(r'(\d{1,2})\s*كونكر\s*(?:قديم|جديد)', text, re.IGNORECASE)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 20:
            conq_count = v

    return {
        'frames_list': found_frames,
        'frames_str':  ','.join(found_frames) if found_frames else '',
        'conqueror_frames_count': conq_count,
        'has_conqueror_frame': bool(found_frames and any('frame_conqueror' in f for f in found_frames)),
        'has_plane_frame':     any(f in found_frames for f in ['frame_plane', 'frame_plane_silver', 'frame_plane_gold']),
        'has_re2_frame':       'frame_re2' in found_frames,
        'has_jodzilla_frame':  'frame_jodzilla' in found_frames,
    }


_RARE_ITEMS = {
    # ── بدلات إكس (X-Suits) ────────────────────────────────
    'xsuit_pharaoh':       r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:الفرعون|فرعون)',
    'xsuit_poseidon':      r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:بوسايد[ونا]+|poseidon)',
    'xsuit_raven_crow':    r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:الغراب|غراب|كرو|crow)',
    'xsuit_silvanus':      r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:سيلفان[وس]*|سلفاتشو|silvanus)',
    'xsuit_anubis':        r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:انوبيس|anubis)',
    'xsuit_joker':         r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:الجوكر|جوكر)',
    'xsuit_drayvion':      r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:درافيون|dravion)',
    'xsuit_mummy':         r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:الموميا|موميا|مومياء)',
    'xsuit_lavinestra':    r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:لفينكيسترا|لاڤنيسترا|lavinestra)',
    'xsuit_seifactus':     r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:سيفاكتوس|seifactus)',
    'xsuit_lion':          r'(?:بدل[هةات]*|لبس[هةات]*|اكس|x)\b[\s\S]{0,20}?(?:الاسد|اسد)',
    'xsuit_generic':       r'(?:بدل[هةات]*|لبس[هةات]*)\s*(?:اكس|x)\b|xsuit|x-suit|x\s*سوت',

    # ── جوكر فوكس / السقوط ────────────────────────────────────────
    'joker_fox_locked':    r'(?:[جچ]وكر\s*فوكس|السقوط|سقوط)\s*(?:مقفوله?|مقفول)',
    'joker_fox_unlocked':  r'(?:[جچ]وكر\s*فوكس|السقوط|سقوط)\s*(?:مفتوح[هة]?)',
    'joker_fox':           r'[جچ]وكر\s*فوكس|السقوط|سقوط|تيشرت\s*[اال]*[جچ]وكر',

    # ── خوذات ميثك ───────────────────────────────────────
    'mummy_helmet':        r'(?:خوذ[هة]|هيلمت)\s*(?:موميا|المومياء|مومياء|الجحيم|راكب\s*الجحيم)',
    'helmet_wings':        r'(?:خوذ[هة]|خوزه)\s*(?:الأجنحه|الاجنحه|أجنحه|اجنحه)',
    'helmet_wok_star':     r'(?:خوذ[هة])\s*(?:وك\s*ستار|wok)',
    'helmet_mythic_rare':  r'(?:خوذ[هة])\s*(?:نادره?|ميثك)',

    # ── لوبي ميثك دائم ───────────────────────────────────
    'lobby_mythic':        r'(?:لوبي|لوبى)\s*(?:ميثك|مثيك)\s*(?:دائم|دايم)',

    # ── شنط (حقائب) ميثك ─────────────────────────────────
    'bag_mythic_joker':    r'(?:شنط[هة]|حقيب[هة])\s*(?:الجوكر|جوكر)',
    'bag_mythic_pharaoh':  r'(?:شنط[هة]|حقيب[هة])\s*(?:الفرعون|فرعون)',
    'bag_mythic_generic':  r'(?:شنط[هة]|حقيب[هة])\s*(?:ميثك|مثيك|نادر)',

    # ── موميا (نادرة جداً) ───────────────────────────────
    'mummy_double':        r'(?:دبل|اثنين|اتنين|2)\s*(?:موميا|مومياء)',
    'mummy_outfit':        r'(?:لبس[هة]|طقم|بدل[هة])\s*(?:موميا|المومياء)',
    'mummy_general':       r'موميا|مومياء',

    # ── لبسات نادرة بالاسم ────────────────────────────────
    'outfit_ghazi':        r'(?:الغازي|غازي)',
    'outfit_ghawas':       r'(?:الغواص|غواص)',
    'outfit_haem':         r'(?:الهائم|هائم)',
    'outfit_captain':      r'(?:القبطان|قبطان)\s*(?:كامل[هة]?)?',
    'outfit_crow':         r'(?:الكرو|كرو)\b',
    'outfit_fireman':      r'(?:المطافي|مطافي)',
    'outfit_joker_full':   r'(?:طقم|لبس[هة])\s*(?:الجوكر|جوكر)',
    'outfit_devil':        r'(?:الشيطان|شيطان)\s*(?:الاحمر)?',
    'outfit_survivor':     r'(?:الناجي|ناجي)\b',
    'outfit_assassin':     r'(?:القاتل|قاتل)\s*(?:المحترف)?',
    'outfit_jodzilla':     r'(?:الجودزيلا|جودزيلا|جوزيلا)',
    'outfit_ananas':       r'(?:الاناناس|الأناناس|اناناس)',
    'outfit_rabbit':       r'(?:الارنب|ارنب)',
    'outfit_soap_double':  r'(?:صابونتين|صابونه\s*سوده\s*وزرقاء|صابونه\s*زرق[هةا]?\s*وسود[هةا]?)',
    'outfit_soap_blue':    r'(?:صابونه|صابونة)\s*(?:الزرقاء|الزرقا|ازرق)',
    'outfit_soap_black':   r'(?:صابونه|صابونة)\s*(?:السوداء|السودا|سودا|سوده|اسود)',
    'outfit_soap_rare':    r'(?:صابونه|صابونة)\s*(?:حمرا|حمراء|صفرا|صفراء|بيضا|بيضاء|احمر|اصفر|ابيض)',
    'outfit_gold':         r'(?:لبس[هة]|طقم)\s*(?:جولد|ذهب)',
    'outfit_silver':       r'(?:لبس[هة]|طقم)\s*(?:فضي|سيلفر)',

    # ── فيس بنت وقصات شعر ────────────────────────────────
    'face_girl':           r'فيس\s*بنت|فيس\s*البنت|وجه\s*بنت',
    'hair_cut_qarnain':    r'شعر\s*قرنين|شعر\s*القرنين',
    'hair_cut_kaboria':    r'شعر\s*(?:ال)?كابوريا|شعر\s*(?:ال)?كبوريا',
    'hair_cut_yellow':     r'شعر\s*اصفر|شعر\s*الاصفر',
    'hair_cuts':           r'قصا?[تة]\s*شعر',

    # ── كونكر وألقاب ─────────────────────────────────────
    'conqueror':           r'كونكر|conqueror',
    'mythic_fashion':      r'ميثك\s*فاشون|mythic\s*fashion',
    'ace_master':          r'ايس\s*ماستر|ace\s*master',

    # ── سيارات نادرة ─────────────────────────────────────
    'car_mclaren':         r'مكلارين|ماكلارين|maclaren|mclaren',
    'car_dodge':           r'دودج|dodge',
    'car_dacia':           r'داسيا|dacia',
    'car_bugatti':         r'بوجاتي|بوغاتي|bugatti',
    'car_lamborghini':     r'لمبورجيني|لامبو|lamborghini',
    'car_jeep':            r'\bجيب\b|jeep',
    'car_porsche':         r'بورش|porsche',
    'car_tesla':           r'تسلا|tesla',
    'car_bentley':         r'بنتلي|bentley',
    'car_dev_fleet':       r'اسطول\s*سيار|سيار[هة]\s*تطوير|عربي[هة]\s*تطوير',

    # ── مميزات إضافية ────────────────────────────────────
    'scarf_tiger':         r'وشاح\s*(?:النمر|نمر|الفهد|فهد)',
    'material_crystal':    r'ماتريال|ماتريل|متريال|كريستال',
    'popularity_million':  r'(?:شعبي[هة]|popularity)\s*(?:مليون|\d+m)',
    'parachute_rare':      r'(?:براشوت|مظله)\s*(?:نادر|ميثك|الغراب|فرعون)',
    'emote_mythic':        r'(?:رقص[هة]|إيموت|موشن|emote)\s*(?:نادر|ميثك)',
}

def extract_rare_items(text: str) -> list:
    """
    استخراج جميع العناصر النادرة الموجودة في النص.
    يتجنب إضافة Parent إذا وُجد Child أكثر تحديداً.
    """
    found = []
    for key, pattern in _RARE_ITEMS.items():
        if re.search(pattern, text, re.IGNORECASE):
            # تجنب الـ parent إذا وُجد ابن أدق
            if key == 'joker_fox' and (
                'joker_fox_locked' in found or 'joker_fox_unlocked' in found
            ):
                continue
            if key == 'xsuit_generic' and any(
                k.startswith('xsuit_') and k != 'xsuit_generic' for k in found
            ):
                continue
            if key == 'mummy_general' and (
                'mummy_double' in found or 'mummy_outfit' in found or 'mummy_helmet' in found
            ):
                continue
            if key == 'hair_cuts' and (
                'hair_cut_qarnain' in found or 'hair_cut_kaboria' in found or 'hair_cut_yellow' in found
            ):
                continue
            if key in ['outfit_soap_blue', 'outfit_soap_black'] and 'outfit_soap_double' in found:
                continue
            found.append(key)
    return found


# ─────────────────────────────────────────────────────────────
# 8. الدالة الرئيسية
# ─────────────────────────────────────────────────────────────

def parse_account_data(raw_text: str, cleaned_text: str) -> dict:
    """
    تجمع جميع المحللات وتُرجع dict موحداً بكل خصائص الحساب.
    """
    arabic_numerals = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    cleaned_text = cleaned_text.translate(arabic_numerals)
    raw_text = raw_text.translate(arabic_numerals)
    
    price_egp, price_usd = extract_prices(cleaned_text)
    m4                   = extract_m4_info(cleaned_text)
    rare                 = extract_rare_items(cleaned_text)
    cars                 = extract_cars_info(cleaned_text)
    frames               = extract_frames_info(cleaned_text)
    weapons              = extract_weapons_detail(cleaned_text)
    companions           = extract_companions(cleaned_text)

    def has(*prefixes):
        return any(any(k.startswith(p) for p in prefixes) for k in rare)

    return {
        "clean_text":       cleaned_text,

        # ── أساسيات الحساب ──
        "account_level":        extract_level(cleaned_text),
        "collection_level":     extract_collection_level(cleaned_text),
        "mythics_count":        extract_mythics(cleaned_text),
        "guns_count":           extract_guns_count(cleaned_text),
        "xsuits_count":         extract_xsuits_count(cleaned_text),

        # ── الأسعار ──
        "price_egp":        price_egp,
        "price_usd":        price_usd,

        # ── الامفور ──
        "m4_type":          m4['m4_type'],
        "m4_level":         m4['m4_level'],
        "m4_is_max":        m4['m4_is_max'],
        "m4_count":         m4.get('m4_count', 0),
        "m4_2_type":        m4.get('m4_2_type'),
        "m4_2_level":       m4.get('m4_2_level'),
        "m4_2_is_max":      m4.get('m4_2_is_max', False),
        "m4_3_type":        m4.get('m4_3_type'),
        "m4_3_level":       m4.get('m4_3_level'),
        "m4_3_is_max":      m4.get('m4_3_is_max', False),

        # ── السيارات ──
        "cars_total":       cars['cars_total'],
        "cars_mythic":      cars['cars_mythic'],
        "has_airdrop_car":  cars['has_airdrop_car'],

        # ── الإطارات ──
        "frames_str":             frames['frames_str'],
        "conqueror_frames_count": frames['conqueror_frames_count'],
        "has_conqueror_frame":    frames['has_conqueror_frame'],
        "has_plane_frame":        frames['has_plane_frame'],
        "has_re2_frame":          frames['has_re2_frame'],

        # ── عناصر نادرة (نص للـ CSV) ──
        "rare_items_str":   ','.join(rare) if rare else '',

        # ── Flags سريعة ──
        "has_xsuit":            has('xsuit_'),
        "has_m4_glacier":       m4['m4_type'] == 'glacier',
        "has_joker_fox":        has('joker_fox'),
        "has_joker_fox_locked": 'joker_fox_locked' in rare,
        "has_mummy":            companions['has_mummy'],
        "has_double_mummy":     companions['has_double_mummy'],
        "has_mummy_helmet":     companions['has_mummy_helmet'],
        "has_conqueror":        companions['has_conqueror'],
        "has_vehicle_dev":      companions['has_vehicle_dev'],
        "has_face_girl":        'face_girl' in rare,
        "has_lobby_mythic":     'lobby_mythic' in rare,
        "has_car_mclaren":      'car_mclaren' in rare,
        "has_car_porsche":      'car_porsche' in rare,
        "has_car_dodge":        'car_dodge' in rare,
        "has_ghazi":            'outfit_ghazi' in rare,
        "has_ghawas":           'outfit_ghawas' in rare,
        "has_soap_blue":        'outfit_soap_blue' in rare,
        "has_soap_black":       'outfit_soap_black' in rare,
        "has_soap_rare":        'outfit_soap_rare' in rare,
        "has_soap_double":      'outfit_soap_double' in rare,
        "has_scarf_tiger":      'scarf_tiger' in rare,
        "has_hair_qarnain":     'hair_cut_qarnain' in rare,
        "has_hair_kaboria":     'hair_cut_kaboria' in rare,
        "has_hair_yellow":      'hair_cut_yellow' in rare,

        # ── تفاصيل الأسلحة ──
        **weapons,

        # ── الرفقاء ──
        **companions,
    }
