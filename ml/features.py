# -*- coding: utf-8 -*-
"""
PUBG Market Intelligence - Feature Engineering & Combo Detection
This module takes basic extracted items and calculates high-level market scores:
Combo Score, Prestige Score, Rarity Score, and Market Demand.
"""

from parser.aliases import KNOWLEDGE_BASE

# Define highly sought-after combinations and their multipliers
LEGENDARY_COMBOS = {
    "glacier_mummy": {
        "items": ["glacier_m416", "mummy_white"], 
        "multiplier": 1.4,
        "description": "Glacier M416 + White Mummy"
    },
    "joker_conqueror": {
        "items": ["joker_m416", "conqueror_old"], 
        "multiplier": 1.3,
        "description": "Joker M416 + Old Conqueror"
    },
    "silver_plane_old_rp": {
        "items": ["frame_plane", "old_rp"], # assuming old_rp will be tracked
        "multiplier": 1.5,
        "description": "Plane Frame + Old RP"
    },
    "double_mummy": {
        "items": ["mummy_white", "mummy_yellow"], 
        "multiplier": 1.6,
        "description": "White & Yellow Mummy"
    },
    "triple_threat": {
        "items": ["glacier_m416", "face_girl", "mummy_white"], 
        "multiplier": 2.0,
        "description": "Glacier + Girl Face + White Mummy"
    },
}

class FeatureEngineer:
    def __init__(self, extracted_items: list):
        """
        extracted_items: list of canonical item IDs from KNOWLEDGE_BASE 
        e.g. ['glacier_m416', 'face_girl', 'mummy_white']
        """
        self.items = set(extracted_items)
        
    def detect_combos(self):
        """
        Detects active combos and returns a list of combo keys and total multiplier.
        """
        active_combos = []
        total_multiplier = 1.0
        
        for combo_id, combo_data in LEGENDARY_COMBOS.items():
            if all(req_item in self.items for req_item in combo_data["items"]):
                active_combos.append(combo_id)
                # Compounding multipliers (could also be additive depending on business logic)
                total_multiplier *= combo_data["multiplier"]
                
        return {
            "combos": active_combos,
            "multiplier": total_multiplier
        }
        
    def calculate_prestige_score(self):
        """
        Calculates total prestige score based on item base prestige values.
        """
        score = 0
        for item in self.items:
            item_data = KNOWLEDGE_BASE.get(item, {})
            score += item_data.get("prestige_score", 0)
        return score
        
    def calculate_rarity_score(self):
        """
        Calculates a rarity score. Mythics add more than legendaries.
        """
        score = 0
        for item in self.items:
            item_data = KNOWLEDGE_BASE.get(item, {})
            rarity = item_data.get("rarity", "common")
            if rarity == "mythic_xsuit":
                score += 50
            elif rarity == "mythic":
                score += 30
            elif rarity == "mythic_vehicle":
                score += 25
            elif rarity == "legendary":
                score += 10
            elif rarity == "epic":
                score += 5
        return score
        
    def calculate_market_score(self):
        """
        Calculates the base market demand score.
        """
        score = 0
        for item in self.items:
            item_data = KNOWLEDGE_BASE.get(item, {})
            score += item_data.get("market_score", 0)
        return score

    def compute_interaction_features(self, parsed_dict: dict = None) -> dict:
        """
        Computes domain-specific interaction features between high-value items and security signals.
        """
        parsed = parsed_dict or {}
        
        has_m4 = bool(parsed.get('has_m4_glacier') or parsed.get('m4_type'))
        m4_is_max = bool(parsed.get('m4_is_max') or (parsed.get('m4_level') and parsed.get('m4_level') >= 7))
        has_mummy = bool(parsed.get('has_mummy') or 'mummy_white' in self.items)
        has_xsuit = bool(parsed.get('has_xsuit') or any(i.startswith('xsuit_') for i in self.items))
        has_face_girl = bool(parsed.get('has_face_girl') or 'face_girl' in self.items)
        
        guns = float(parsed.get('guns_count') or 0)
        mythics = float(parsed.get('mythics_count') or 0)
        
        has_internal = 1.0 if parsed.get('has_internal_link') else 0.0
        is_fb_disabled = 1.0 if parsed.get('is_facebook_disabled') else 0.0
        has_middleman = 1.0 if parsed.get('has_trusted_middleman') else 0.0
        
        return {
            "has_m4_max_x_mummy": 1.0 if (m4_is_max and has_mummy) else 0.0,
            "has_m4_x_xsuit": 1.0 if (has_m4 and has_xsuit) else 0.0,
            "guns_per_mythic_ratio": round(guns / (mythics + 1.0), 3),
            "has_super_combo": 1.0 if ("glacier_m416" in self.items and "face_girl" in self.items and "mummy_white" in self.items) else 0.0,
            "has_internal_link": has_internal,
            "is_facebook_disabled": is_fb_disabled,
            "has_trusted_middleman": has_middleman,
        }

    def extract_all_features(self, parsed_dict: dict = None):
        combo_data = self.detect_combos()
        interactions = self.compute_interaction_features(parsed_dict)
        
        base_dict = {
            "prestige_score": self.calculate_prestige_score(),
            "rarity_score": self.calculate_rarity_score(),
            "base_market_score": self.calculate_market_score(),
            "combo_multiplier": combo_data["multiplier"],
            "active_combos": combo_data["combos"],
            "final_market_score": self.calculate_market_score() * combo_data["multiplier"]
        }
        base_dict.update(interactions)
        return base_dict


