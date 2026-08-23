# -*- coding: utf-8 -*-
"""
PUBG Market Intelligence - Unified Feature Pipeline
Centralized pipeline for parsing text, resolving canonical aliases, 
extracting engineered features, and preparing vectors for model training and inference.
"""

from typing import Dict, Any, Tuple, List
from parser.text_cleaner import clean_text
from parser.regex_parser import parse_account_data
from parser.aliases import resolve_text_items
from parser.extractors.security import SecurityExtractor
from ml.features import FeatureEngineer
from schemas.account import ParsedAccountSchema

class FeaturePipeline:
    def __init__(self):
        self.security_extractor = SecurityExtractor()

    def extract_canonical_items(self, parsed_data: Dict[str, Any], raw_text: str) -> List[str]:
        """
        Extracts canonical item IDs from both parsed structured flags and raw/clean text.
        """
        items = set()
        
        # Explicit flags from parser
        if parsed_data.get("has_m4_glacier") or parsed_data.get("m4_type") == "glacier":
            items.add("glacier_m416")
        if parsed_data.get("has_joker_fox") or parsed_data.get("m4_type") == "joker":
            items.add("joker_m416")
        if parsed_data.get("has_mummy"):
            items.add("mummy_white")
        if parsed_data.get("has_conqueror"):
            items.add("conqueror_old")
        if parsed_data.get("has_face_girl"):
            items.add("face_girl")
        if parsed_data.get("has_xsuit"):
            items.add("xsuit_pharaoh")
        if parsed_data.get("has_car_mclaren"):
            items.add("mclaren")
        if parsed_data.get("has_car_dodge"):
            items.add("dodge")
        if parsed_data.get("has_car_porsche"):
            items.add("porsche")
            
        # Text-based fuzzy/exact resolution
        text_items = resolve_text_items(raw_text)
        items.update(text_items)
        
        return list(items)

    def process(self, raw_text: str) -> Dict[str, Any]:
        """
        Runs full pipeline on a raw text string.
        Returns a complete feature dictionary including parsed metadata, intelligence scores, security signals, and canonical items.
        """
        cleaned = clean_text(raw_text or "")
        parsed = parse_account_data(raw_text or "", cleaned)
        security_info = self.security_extractor.extract(cleaned)
        
        parsed.update(security_info)
        canonical_items = self.extract_canonical_items(parsed, raw_text or "")
        
        engineer = FeatureEngineer(canonical_items)
        intel = engineer.extract_all_features(parsed_dict=parsed)
        
        # Merge structured features, canonical items, security info, and intelligence scores
        result = dict(parsed)
        result["clean_text"] = cleaned
        result["canonical_items"] = canonical_items
        result["extracted_items_str"] = ",".join(canonical_items)
        result["active_combos_str"] = ",".join(intel["active_combos"])
        result.update(intel)
        
        # Validate through Pydantic schema
        schema = ParsedAccountSchema(**result)
        validated_dict = schema.model_dump()
        validated_dict.update(result)
        
        return validated_dict

# Singleton instance for easy import
pipeline_instance = FeaturePipeline()
