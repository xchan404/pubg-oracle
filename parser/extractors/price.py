"""
Price Extractor Module
Extracts EGP and USD prices with support for k/K notation and Arabic thousand multipliers.
"""

import re
from typing import Any

from parser.extractors.base import BaseExtractor


class PriceExtractor(BaseExtractor):
    @staticmethod
    def parse_numeric_value(raw_val: str) -> float | None:
        """Converts strings like '15k', '15.5k', '15 الف', '15,000' to float."""
        if not raw_val:
            return None
        val_str = raw_val.strip().lower()

        k_match = re.search(r'(\d[\d,\.]*)\s*k\b', val_str, re.IGNORECASE)
        if k_match:
            try:
                return float(k_match.group(1).replace(',', '')) * 1000.0
            except ValueError:
                pass

        thousand_match = re.search(r'(\d[\d,\.]*)\s*(?:ألف|الف)\b', val_str, re.IGNORECASE)
        if thousand_match:
            try:
                return float(thousand_match.group(1).replace(',', '')) * 1000.0
            except ValueError:
                pass

        plain_match = re.search(r'(\d[\d,\.]*)', val_str)
        if plain_match:
            try:
                return float(plain_match.group(1).replace(',', ''))
            except ValueError:
                pass

        return None

    def extract_prices(self, text: str) -> tuple[float | None, float | None]:
        price_egp, price_usd = None, None

        usd_match = re.search(r'(?:\$\s*(\d[\d,\.]*)|(\d[\d,\.]*)\s*\$)', text)
        if usd_match:
            raw_usd = usd_match.group(1) or usd_match.group(2)
            try:
                price_usd = float(raw_usd.replace(',', ''))
            except ValueError:
                pass

        price_kw = r'السعر|الثمن|سعره|بسعر|قيمته|بكام|طالب|price'
        m = re.search(
            r'(?:' + price_kw + r')\s*[:=\-\u061f:]*\s*(.{1,120})',
            text, re.IGNORECASE
        )

        search_target = m.group(1) if m else text

        egp_explicit = re.search(
            r'(\d[\d,\.]*\s*(?:k|الف|ألف)?)\s*(?:ج(?:نيه|ينيه)?|EGP|egp)\b',
            search_target, re.IGNORECASE
        )
        if egp_explicit:
            price_egp = self.parse_numeric_value(egp_explicit.group(1))

        if not price_egp:
            k_explicit = re.search(r'\b(\d[\d,\.]*\s*k)\b', search_target, re.IGNORECASE)
            if k_explicit:
                price_egp = self.parse_numeric_value(k_explicit.group(1))

        if not price_egp and m:
            candidates = re.findall(r'\b\d[\d,\.]*(?:\s*k|\s*الف|\s*ألف)?\b', search_target, re.IGNORECASE)
            for cand in candidates:
                v = self.parse_numeric_value(cand)
                if v and v > 100:
                    if price_usd and abs(v - price_usd) < 0.1:
                        continue
                    price_egp = v
                    break

        if not price_egp and not m:
            direct_egp = re.search(
                r'(\d[\d,\.]*\s*(?:k|الف|ألف)?)\s*(?:ج(?:نيه|ينيه)?|EGP|egp)\b',
                text, re.IGNORECASE
            )
            if direct_egp:
                price_egp = self.parse_numeric_value(direct_egp.group(1))

        return price_egp, price_usd

    def extract(self, text: str) -> dict[str, Any]:
        price_egp, price_usd = self.extract_prices(text)
        return {
            "price_egp": price_egp,
            "price_usd": price_usd
        }
