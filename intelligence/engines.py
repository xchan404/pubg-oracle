"""
PUBG Market Intelligence Engines
Contains engines for calculating item rarity, demand, combos, and trends based on historical data.
"""

import logging

from sqlalchemy import func

from database.db import SessionLocal
from database.models import ParsedAccount
from parser.aliases import KNOWLEDGE_BASE

logger = logging.getLogger("pubg_intelligence")

class RarityEngine:
    """
    Calculates dynamic rarity based on the frequency of items in the parsed database.
    """
    def __init__(self):
        self.db = SessionLocal()

    def calculate_rarities(self):
        # Count total accounts
        total_accounts = self.db.query(ParsedAccount).count()
        if total_accounts == 0:
            return {}

        # This would realistically parse extracted_items_str and count frequencies.
        # For now, it returns the base rarity scores from the knowledge base,
        # but the architecture is here to do dynamic rarity adjustments.
        rarities = {}
        for item_id, data in KNOWLEDGE_BASE.items():
            base_score = data.get("prestige_score", 0)
            # Future: adjust base_score based on frequency
            # (e.g., if total_accounts > 1000 and item appears 10 times -> +20% rarity bonus)
            rarities[item_id] = base_score

        self.db.close()
        return rarities

class DemandEngine:
    """
    Tracks demand by looking at how quickly items sell (if we track sold status)
    or by search frequency.
    """
    def get_demand_multiplier(self, item_id: str) -> float:
        # Example: Glacier M4 is high demand
        if "glacier" in item_id:
            return 1.5
        if "mummy" in item_id:
            return 1.4
        return 1.0

class TrendAnalyzer:
    """
    Analyzes price trends over time.
    """
    def __init__(self):
        self.db = SessionLocal()

    def get_average_price_for_item(self, item_id: str):
        """
        Calculates the average price of accounts containing a specific item.
        """
        # Note: This is an expensive operation if done per-item without caching.
        # Requires LIKE queries on the JSON/text field.
        result = self.db.query(func.avg(ParsedAccount.price_egp)).filter(
            ParsedAccount.extracted_items_str.like(f"%{item_id}%"),
            ParsedAccount.price_egp > 0
        ).scalar()

        self.db.close()
        return result or 0.0
