# -*- coding: utf-8 -*-
"""
PUBG Market Intelligence - Knowledge Base
This module contains the master dictionary of all valuable items in the game.
Each item has a list of aliases, its rarity, category, prestige score, and base market score.
"""

from typing import Optional

KNOWLEDGE_BASE = {
    # ==========================
    # Weapon Skins (M416)
    # ==========================
    "glacier_m416": {
        "aliases": ["جليشر", "امفور تلجي", "تلجي", "ثلجي", "glacier", "التلجيه", "التلجية", "بينور", "جلشر"],
        "rarity": "legendary",
        "category": "weapon_m416",
        "prestige_score": 95,
        "market_score": 10.0
    },
    "joker_m416": {
        "aliases": ["جوكر", "امفور جوكر", "joker", "الجوكر"],
        "rarity": "legendary",
        "category": "weapon_m416",
        "prestige_score": 85,
        "market_score": 8.5
    },
    "roaring_lizard_m416": {
        "aliases": ["السحليه", "السحلية", "امفور السحليه", "السحليه الذهبيه", "سحليه"],
        "rarity": "mythic",
        "category": "weapon_m416",
        "prestige_score": 80,
        "market_score": 8.0
    },
    "call_of_wild_m416": {
        "aliases": ["نداء البريه", "نداء البرية", "البريه"],
        "rarity": "legendary",
        "category": "weapon_m416",
        "prestige_score": 75,
        "market_score": 7.5
    },
    "imperial_splendor_m416": {
        "aliases": ["الامبراطور", "امبراطور", "imperial", "الامبراطوره", "الامبراطوريه"],
        "rarity": "mythic",
        "category": "weapon_m416",
        "prestige_score": 75,
        "market_score": 7.5
    },
    "techno_core_m416": {
        "aliases": ["الرحاله", "الرحالة", "رحاله"],
        "rarity": "legendary",
        "category": "weapon_m416",
        "prestige_score": 70,
        "market_score": 7.0
    },
    "wandering_tyrant_m416": {
        "aliases": ["الطاغيه", "الطاغية", "طاغيه"],
        "rarity": "legendary",
        "category": "weapon_m416",
        "prestige_score": 65,
        "market_score": 6.5
    },
    
    # ==========================
    # Other Premium Guns
    # ==========================
    "blood_tooth_vector": {
        "aliases": ["فكتور الخفاش", "الخفاش", "دم الخفاش", "blood tooth"],
        "rarity": "legendary",
        "category": "weapon_other",
        "prestige_score": 60,
        "market_score": 6.0
    },
    "hellfire_akm": {
        "aliases": ["فزاعه", "فزاعة", "اي كي فزاعه", "akm فزاعه", "hellfire"],
        "rarity": "legendary",
        "category": "weapon_other",
        "prestige_score": 75,
        "market_score": 7.5
    },
    "seven_seas_akm": {
        "aliases": ["بحار", "البحار", "بحار السبعه", "seven seas"],
        "rarity": "legendary",
        "category": "weapon_other",
        "prestige_score": 65,
        "market_score": 6.5
    },
    "eight_bit_uzi": {
        "aliases": ["اوزي الشبح", "شبح", "8-bit", "8 bit"],
        "rarity": "legendary",
        "category": "weapon_other",
        "prestige_score": 60,
        "market_score": 5.5
    },
    
    # ==========================
    # X-Suits
    # ==========================
    "xsuit_pharaoh": {
        "aliases": ["فرعون", "الفرعون", "الفرعونيه", "pharaoh"],
        "rarity": "mythic_xsuit",
        "category": "xsuit",
        "prestige_score": 100,
        "market_score": 10.0
    },
    "xsuit_blood_raven": {
        "aliases": ["غراب", "الغراب", "دم الغراب", "blood raven", "raven"],
        "rarity": "mythic_xsuit",
        "category": "xsuit",
        "prestige_score": 90,
        "market_score": 9.0
    },
    "xsuit_poseidon": {
        "aliases": ["بوسيدون", "بوسيدن", "poseidon"],
        "rarity": "mythic_xsuit",
        "category": "xsuit",
        "prestige_score": 85,
        "market_score": 8.5
    },
    "xsuit_avalanche": {
        "aliases": ["انهيار", "الانهيار", "الجليديه", "avalanche"],
        "rarity": "mythic_xsuit",
        "category": "xsuit",
        "prestige_score": 85,
        "market_score": 8.5
    },
    "xsuit_silvanus": {
        "aliases": ["سيلفانوس", "سلفانوس", "الغابه", "silvanus"],
        "rarity": "mythic_xsuit",
        "category": "xsuit",
        "prestige_score": 80,
        "market_score": 8.0
    },
    "xsuit_arcane_jester": {
        "aliases": ["المهرج", "مهرج اكس", "مهرج اكستريم", "arcane jester", "jester"],
        "rarity": "mythic_xsuit",
        "category": "xsuit",
        "prestige_score": 80,
        "market_score": 8.0
    },
    
    # ==========================
    # Outfits (Rare)
    # ==========================
    "mummy_white": {
        "aliases": ["موميا بيضا", "مومياء بيضاء", "الموميا البيضا", "المومياء البيضاء", "موميا"],
        "rarity": "mythic",
        "category": "outfit",
        "prestige_score": 95,
        "market_score": 9.5
    },
    "mummy_yellow": {
        "aliases": ["موميا صفرا", "مومياء صفراء", "الموميا الصفرا", "المومياء الصفراء"],
        "rarity": "mythic",
        "category": "outfit",
        "prestige_score": 95,
        "market_score": 9.5
    },
    "bape_yellow": {
        "aliases": ["بيب اصفر", "البيب الاصفر", "bape اصفر", "bape yellow"],
        "rarity": "mythic",
        "category": "outfit",
        "prestige_score": 90,
        "market_score": 8.5
    },
    "bape_mix": {
        "aliases": ["بيب مكس", "البيب المكس", "bape mix", "بيب مشكل"],
        "rarity": "mythic",
        "category": "outfit",
        "prestige_score": 90,
        "market_score": 8.5
    },
    "godzilla_suit": {
        "aliases": ["جودزيلا", "جودزلا", "بدلة جودزيلا", "godzilla"],
        "rarity": "legendary",
        "category": "outfit",
        "prestige_score": 75,
        "market_score": 7.0
    },
    
    # ==========================
    # Vehicles (Cars)
    # ==========================
    "mclaren": {
        "aliases": ["ماكلارين", "مكلارين", "mclaren", "ماك لارين"],
        "rarity": "mythic_vehicle",
        "category": "vehicle",
        "prestige_score": 80,
        "market_score": 8.0
    },
    "tesla": {
        "aliases": ["تسلا", "تيسلا", "tesla"],
        "rarity": "mythic_vehicle",
        "category": "vehicle",
        "prestige_score": 75,
        "market_score": 7.5
    },
    "dodge": {
        "aliases": ["دوج", "دوجة", "دودج", "dodge"],
        "rarity": "mythic_vehicle",
        "category": "vehicle",
        "prestige_score": 70,
        "market_score": 7.0
    },
    "bugatti": {
        "aliases": ["بوجاتي", "بوقاتي", "bugatti"],
        "rarity": "mythic_vehicle",
        "category": "vehicle",
        "prestige_score": 85,
        "market_score": 8.5
    },
    "koenigsegg": {
        "aliases": ["كونيجسيج", "كونيغسيغ", "koenigsegg", "كوني"],
        "rarity": "mythic_vehicle",
        "category": "vehicle",
        "prestige_score": 80,
        "market_score": 8.0
    },
    
    # ==========================
    # Conqueror Titles / Frames
    # ==========================
    "conqueror_old": {
        "aliases": ["كونكر قديم", "كونكر سيزون 2", "كونكر سيزون 3", "كونكر سيزون 4", "كونكر سيزون 5", "كونكر سيزون 6"],
        "rarity": "legendary",
        "category": "title",
        "prestige_score": 90,
        "market_score": 9.0
    },
    "conqueror_new": {
        "aliases": ["كونكر جديد", "كونكر", "غازي"],
        "rarity": "epic",
        "category": "title",
        "prestige_score": 60,
        "market_score": 4.0
    },
    "frame_plane": {
        "aliases": ["اطار طياره", "اطار طيارة", "فريم طياره"],
        "rarity": "mythic",
        "category": "frame",
        "prestige_score": 70,
        "market_score": 6.0
    },
    "frame_re2": {
        "aliases": ["اطار ريزدنت", "اطار زومبي", "فريم ريزدنت", "re2"],
        "rarity": "mythic",
        "category": "frame",
        "prestige_score": 75,
        "market_score": 6.5
    },
    
    # ==========================
    # Hair / Beards / Faces
    # ==========================
    "face_girl": {
        "aliases": ["فيس البنت", "وجه البنت", "وش البنت", "الفيس", "فيس"],
        "rarity": "legendary",
        "category": "cosmetic",
        "prestige_score": 85,
        "market_score": 8.0
    },
    "beard": {
        "aliases": ["لحيه", "اللحيه", "دقن", "الدقن"],
        "rarity": "legendary",
        "category": "cosmetic",
        "prestige_score": 80,
        "market_score": 7.5
    },
    "hair_qarnain": {
        "aliases": ["شعر قرنين", "قرنين", "ابو قرنين"],
        "rarity": "epic",
        "category": "cosmetic",
        "prestige_score": 65,
        "market_score": 5.0
    },
    "hair_kaboria": {
        "aliases": ["كابوريا", "شعر كابوريا"],
        "rarity": "epic",
        "category": "cosmetic",
        "prestige_score": 60,
        "market_score": 4.5
    },
}

def resolve_alias(word: str, similarity_threshold: float = 0.82) -> Optional[str]:
    """
    Given a word or phrase, returns the canonical item ID from KNOWLEDGE_BASE.
    Uses exact matching first, followed by fuzzy string matching.
    """
    if not word or not isinstance(word, str):
        return None
        
    word_clean = word.strip().lower()
    if not word_clean:
        return None
        
    # 1. Exact match check
    for item_id, data in KNOWLEDGE_BASE.items():
        if word_clean in [a.lower() for a in data["aliases"]]:
            return item_id
            
    # 2. Fuzzy match fallback
    import difflib
    best_match = None
    best_ratio = 0.0

    for item_id, data in KNOWLEDGE_BASE.items():
        for alias in data["aliases"]:
            alias_lower = alias.lower()
            # Calculate similarity
            ratio = difflib.SequenceMatcher(None, word_clean, alias_lower).ratio()
            if ratio > best_ratio and ratio >= similarity_threshold:
                best_ratio = ratio
                best_match = item_id

    return best_match


def resolve_text_items(text: str) -> list:
    """
    Scans a given text string and resolves all canonical items present in it.
    Returns a list of unique canonical item IDs.
    """
    if not text:
        return []
        
    found_items = set()
    text_lower = text.lower()
    
    for item_id, data in KNOWLEDGE_BASE.items():
        for alias in data["aliases"]:
            if alias.lower() in text_lower:
                found_items.add(item_id)
                break
                
    return list(found_items)


def get_item_info(item_id: str) -> dict:
    """Returns metadata for a given canonical item ID."""
    return KNOWLEDGE_BASE.get(item_id, {})

