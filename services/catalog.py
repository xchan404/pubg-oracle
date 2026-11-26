"""
Offer catalog (Week 3)

One place for what we sell, its price per currency, and what a payment grants.
The bot displays from here; payment approval grants from here. Prices are
per-market (Egypt vs GCC) as locked in the business plan.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Offer:
    code: str
    title_ar: str
    days: int              # 0 for credit packs
    credits: int | None
    prices: dict[str, float]


OFFERS: dict[str, Offer] = {
    "pro_monthly": Offer(
        code="pro_monthly",
        title_ar="Pro شهري",
        days=30,
        credits=None,
        prices={"EGP": 299.0, "SAR": 79.0, "AED": 79.0, "USD": 19.0},
    ),
    "pro_annual": Offer(
        code="pro_annual",
        title_ar="Pro سنوي",
        days=365,
        credits=None,
        prices={"EGP": 2499.0, "SAR": 699.0, "AED": 699.0, "USD": 149.0},
    ),
    "business": Offer(
        code="business",
        title_ar="Business",
        days=30,
        credits=None,
        prices={"EGP": 1999.0, "SAR": 499.0, "AED": 499.0, "USD": 129.0},
    ),
    "credits_5": Offer(
        code="credits_5",
        title_ar="5 استعلامات",
        days=0,
        credits=5,
        prices={"EGP": 75.0, "SAR": 25.0, "AED": 25.0, "USD": 7.0},
    ),
}

DEFAULT_CURRENCY = "EGP"
CURRENCY_BY_COUNTRY = {"EG": "EGP", "SA": "SAR", "AE": "AED"}


def get_offer(code: str) -> Offer | None:
    return OFFERS.get(code)


def resolve_price(offer: Offer, currency: str | None) -> float:
    """Falls back to EGP when a currency has no explicit price."""
    return offer.prices.get((currency or DEFAULT_CURRENCY).upper(), offer.prices[DEFAULT_CURRENCY])


def offer_grants(code: str | None) -> tuple[str | None, int | None, int | None]:
    """Maps an offer code to (plan, days, credits) for payment approval."""
    offer = get_offer(code or "")
    if offer is None:
        return None, None, None
    if offer.credits:
        return None, None, offer.credits
    return offer.code, offer.days, None
