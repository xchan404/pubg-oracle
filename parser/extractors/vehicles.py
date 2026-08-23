# -*- coding: utf-8 -*-
"""
Vehicle Extractor Module
Extracts vehicle count, mythic vehicles, development cars, and airdrop cars.
"""

from typing import Dict, Any
from parser.extractors.base import BaseExtractor
from parser.regex_parser import extract_cars_info

class VehicleExtractor(BaseExtractor):
    def extract(self, text: str) -> Dict[str, Any]:
        cars = extract_cars_info(text)
        return {
            "cars_total": cars.get('cars_total'),
            "cars_mythic": cars.get('cars_mythic'),
            "has_airdrop_car": cars.get('has_airdrop_car', False)
        }
