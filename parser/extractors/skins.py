# -*- coding: utf-8 -*-
"""
Skins Extractor Module
Extracts M416 skin info, lab weapons details, X-suits, and rare outfits.
"""

from typing import Dict, Any
from parser.extractors.base import BaseExtractor
from parser.regex_parser import (
    extract_m4_info,
    extract_weapons_detail,
    extract_xsuits_count,
    extract_rare_items,
    extract_guns_count
)

class SkinExtractor(BaseExtractor):
    def extract(self, text: str) -> Dict[str, Any]:
        m4 = extract_m4_info(text)
        weapons = extract_weapons_detail(text)
        xsuits_count = extract_xsuits_count(text)
        rare_items = extract_rare_items(text)
        guns_count = extract_guns_count(text)
        
        return {
            "m4_type": m4.get('m4_type'),
            "m4_level": m4.get('m4_level'),
            "m4_is_max": m4.get('m4_is_max', False),
            "m4_count": m4.get('m4_count', 0),
            "m4_2_type": m4.get('m4_2_type'),
            "m4_2_level": m4.get('m4_2_level'),
            "m4_2_is_max": m4.get('m4_2_is_max', False),
            "m4_3_type": m4.get('m4_3_type'),
            "m4_3_level": m4.get('m4_3_level'),
            "m4_3_is_max": m4.get('m4_3_is_max', False),
            "xsuits_count": xsuits_count,
            "guns_count": guns_count,
            "rare_items": rare_items,
            "rare_items_str": ','.join(rare_items) if rare_items else '',
            **weapons
        }
