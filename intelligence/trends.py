# -*- coding: utf-8 -*-
"""
PUBG Market Intelligence - Market Trends & Price Analytics Engine
Computes item frequency, price distributions, rarity heatmaps,
and market demand signals from historical parsed account data.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional


CSV_PATH = os.path.join('data', 'parsed', 'csv', 'all_parsed_accounts.csv')

# Item columns to track
ITEM_COLUMNS = {
    'has_m4_glacier': 'Glacier M416',
    'has_joker_fox': 'Joker Fox M416',
    'has_xsuit': 'X-Suit',
    'has_mummy': 'Mummy Outfit',
    'has_double_mummy': 'Double Mummy',
    'has_conqueror': 'Conqueror Title',
    'has_face_girl': 'Girl Face',
    'has_car_mclaren': 'McLaren Car',
    'has_car_porsche': 'Porsche Car',
    'has_car_dodge': 'Dodge Car',
    'has_ghazi': 'Ghazi Outfit',
    'has_ghawas': 'Ghawas Outfit',
    'has_lobby_mythic': 'Mythic Lobby',
    'has_scarf_tiger': 'Tiger Scarf',
    'has_soap_blue': 'Blue Soap',
    'has_soap_black': 'Black Soap',
    'has_soap_double': 'Double Soap',
}

M4_TYPES = {
    'glacier': 'Glacier',
    'joker': 'Joker',
    'aether': 'Aether',
    'tiger': 'Tiger',
    'mummy': 'Mummy',
    'snoopy': 'Snoopy',
    'fire': 'Fire',
    'master': 'Master',
    'piranha': 'Piranha',
    'emperor': 'Emperor',
    'silver': 'Silver',
    'water': 'Water',
}


class MarketTrendsEngine:
    def __init__(self, csv_path: str = CSV_PATH):
        self.csv_path = csv_path
        self._df = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = pd.read_csv(self.csv_path, low_memory=False)
        return self._df

    def get_market_summary(self) -> Dict[str, Any]:
        """Returns a high-level market overview."""
        data = self.df
        priced = data[data['price_egp'].notna() & (data['price_egp'] > 0)]

        return {
            "total_listings": len(data),
            "priced_listings": len(priced),
            "price_detection_rate": round(len(priced) / len(data) * 100, 1),
            "avg_price_egp": round(priced['price_egp'].mean(), 0),
            "median_price_egp": round(priced['price_egp'].median(), 0),
            "min_price_egp": round(priced['price_egp'].min(), 0),
            "max_price_egp": round(priced['price_egp'].max(), 0),
            "channels_count": data['channel_username'].nunique(),
            "channels": data['channel_username'].value_counts().head(10).to_dict(),
        }

    def get_price_distribution(self, bins: int = 10) -> Dict[str, Any]:
        """Returns price distribution breakdown across segments."""
        priced = self.df[self.df['price_egp'].notna() & (self.df['price_egp'] > 0) & (self.df['price_egp'] < 200000)]

        segments = {
            "budget_0_2k": len(priced[priced['price_egp'] < 2000]),
            "economy_2k_5k": len(priced[(priced['price_egp'] >= 2000) & (priced['price_egp'] < 5000)]),
            "mid_5k_10k": len(priced[(priced['price_egp'] >= 5000) & (priced['price_egp'] < 10000)]),
            "premium_10k_20k": len(priced[(priced['price_egp'] >= 10000) & (priced['price_egp'] < 20000)]),
            "whale_20k_50k": len(priced[(priced['price_egp'] >= 20000) & (priced['price_egp'] < 50000)]),
            "ultra_50k_plus": len(priced[priced['price_egp'] >= 50000]),
        }

        return {
            "total_priced": len(priced),
            "segments": segments,
            "percentiles": {
                "p10": round(priced['price_egp'].quantile(0.10), 0),
                "p25": round(priced['price_egp'].quantile(0.25), 0),
                "p50": round(priced['price_egp'].quantile(0.50), 0),
                "p75": round(priced['price_egp'].quantile(0.75), 0),
                "p90": round(priced['price_egp'].quantile(0.90), 0),
                "p99": round(priced['price_egp'].quantile(0.99), 0),
            }
        }

    def get_item_frequency(self) -> List[Dict[str, Any]]:
        """Returns item frequency counts and percentage across all listings."""
        data = self.df
        total = len(data)
        items = []

        for col, label in ITEM_COLUMNS.items():
            if col in data.columns:
                count = int(data[col].fillna(0).astype(bool).sum())
                items.append({
                    "item": label,
                    "column": col,
                    "count": count,
                    "percentage": round(count / total * 100, 2),
                })

        items.sort(key=lambda x: x['count'], reverse=True)
        return items

    def get_m4_type_distribution(self) -> List[Dict[str, Any]]:
        """Returns M4 skin type distribution."""
        data = self.df
        m4_data = data[data['m4_type'].notna() & (data['m4_type'] != '')]
        total_m4 = len(m4_data)

        dist = []
        for m4_type, label in M4_TYPES.items():
            count = int((m4_data['m4_type'] == m4_type).sum())
            if count > 0:
                dist.append({
                    "type": label,
                    "code": m4_type,
                    "count": count,
                    "percentage": round(count / total_m4 * 100, 1) if total_m4 > 0 else 0,
                })

        dist.sort(key=lambda x: x['count'], reverse=True)
        return dist

    def get_item_price_impact(self) -> List[Dict[str, Any]]:
        """
        Calculates the average price uplift for each rare item.
        Compares median price of accounts WITH the item vs accounts WITHOUT.
        """
        priced = self.df[self.df['price_egp'].notna() & (self.df['price_egp'] > 0) & (self.df['price_egp'] < 200000)]
        baseline_median = priced['price_egp'].median()

        impacts = []
        for col, label in ITEM_COLUMNS.items():
            if col not in priced.columns:
                continue

            has_item = priced[priced[col].fillna(0).astype(bool)]
            no_item = priced[~priced[col].fillna(0).astype(bool)]

            if len(has_item) < 10:
                continue

            median_with = has_item['price_egp'].median()
            median_without = no_item['price_egp'].median()
            uplift = median_with - median_without
            pct_uplift = round(uplift / median_without * 100, 1) if median_without > 0 else 0

            impacts.append({
                "item": label,
                "accounts_with": len(has_item),
                "median_price_with": round(median_with, 0),
                "median_price_without": round(median_without, 0),
                "price_uplift_egp": round(uplift, 0),
                "price_uplift_pct": pct_uplift,
            })

        impacts.sort(key=lambda x: x['price_uplift_egp'], reverse=True)
        return impacts

    def get_rarity_demand_heatmap(self) -> List[Dict[str, Any]]:
        """
        Generates a rarity × demand heatmap for each item.
        Rarity = inverse of frequency. Demand = price uplift when present.
        """
        freq = {i['column']: i for i in self.get_item_frequency()}
        impact = {ITEM_COLUMNS.get(i['item'], i['item']): i for i in self.get_item_price_impact()}

        heatmap = []
        for col, label in ITEM_COLUMNS.items():
            f = freq.get(col, {})
            imp = impact.get(label, {})

            frequency_pct = f.get('percentage', 0)
            rarity_score = round(100 - frequency_pct, 1) if frequency_pct > 0 else 100
            demand_score = min(100, max(0, imp.get('price_uplift_pct', 0)))

            heatmap.append({
                "item": label,
                "rarity_score": rarity_score,
                "demand_score": demand_score,
                "frequency_pct": frequency_pct,
                "price_uplift_egp": imp.get('price_uplift_egp', 0),
                "signal": "HOT" if rarity_score > 90 and demand_score > 30 else
                          "WARM" if rarity_score > 80 or demand_score > 20 else
                          "COOL"
            })

        heatmap.sort(key=lambda x: (x['rarity_score'] + x['demand_score']), reverse=True)
        return heatmap

    def get_full_report(self) -> Dict[str, Any]:
        """Returns the complete market trends report."""
        return {
            "market_summary": self.get_market_summary(),
            "price_distribution": self.get_price_distribution(),
            "item_frequency": self.get_item_frequency(),
            "m4_distribution": self.get_m4_type_distribution(),
            "item_price_impact": self.get_item_price_impact(),
            "rarity_demand_heatmap": self.get_rarity_demand_heatmap(),
        }


# Singleton
trends_engine = MarketTrendsEngine()


if __name__ == "__main__":
    import io, json
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    engine = MarketTrendsEngine()

    print("=" * 60)
    print("  PUBG Market Trends & Analytics Report")
    print("=" * 60)

    summary = engine.get_market_summary()
    print(f"\n  Total Listings        : {summary['total_listings']:,}")
    print(f"  Priced Listings       : {summary['priced_listings']:,} ({summary['price_detection_rate']}%)")
    print(f"  Average Price         : {summary['avg_price_egp']:,.0f} EGP")
    print(f"  Median Price          : {summary['median_price_egp']:,.0f} EGP")

    dist = engine.get_price_distribution()
    print(f"\n--- Price Segments ---")
    for seg, count in dist['segments'].items():
        print(f"  {seg:20s}: {count:,}")

    print(f"\n--- Item Frequency (Top 15) ---")
    for item in engine.get_item_frequency()[:15]:
        print(f"  {item['item']:25s}: {item['count']:,} ({item['percentage']}%)")

    print(f"\n--- M4 Skin Distribution ---")
    for m4 in engine.get_m4_type_distribution():
        print(f"  {m4['type']:15s}: {m4['count']:,} ({m4['percentage']}%)")

    print(f"\n--- Item Price Impact (Top 10) ---")
    for imp in engine.get_item_price_impact()[:10]:
        print(f"  {imp['item']:25s}: +{imp['price_uplift_egp']:,.0f} EGP ({imp['price_uplift_pct']:+.1f}%) | "
              f"With: {imp['median_price_with']:,.0f} vs Without: {imp['median_price_without']:,.0f}")

    print(f"\n--- Rarity x Demand Heatmap ---")
    for h in engine.get_rarity_demand_heatmap():
        print(f"  [{h['signal']:4s}] {h['item']:25s}: Rarity={h['rarity_score']:.0f} | Demand={h['demand_score']:.0f} | Uplift={h['price_uplift_egp']:+,.0f} EGP")

    print("\n" + "=" * 60)
