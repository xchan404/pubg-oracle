"""
Canonical Domain Models
Shared vocabulary for listings, sellers, and price observations across
scraper, parser, ML, API, and bot. These complement ParsedAccountSchema
(the parser output contract) with cross-module domain entities.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ChannelType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    GROUP = "group"
    UNKNOWN = "unknown"


class DealVerdict(StrEnum):
    GREAT_DEAL = "GREAT_DEAL"
    FAIR_DEAL = "FAIR_DEAL"
    OVERPRICED = "OVERPRICED"
    UNPRICED = "UNPRICED"


class Seller(BaseModel):
    model_config = ConfigDict(extra="allow")

    telegram_user_id: int | None = None
    display_name: str | None = None
    channel_username: str | None = None
    trust_score: float = 50.0  # 0-100, refined by Phase 2 reputation engine


class Listing(BaseModel):
    """A single sale post as observed in the wild."""
    model_config = ConfigDict(extra="allow")

    channel_username: str
    message_id: int
    posted_at: datetime | None = None
    raw_text: str
    views: int = 0
    forwards: int = 0

    # Lifecycle (populated by the Phase 2 dedup/fingerprinting engine)
    fingerprint: str | None = None
    is_repost_of: str | None = Field(
        None, description="fingerprint of the original listing if this is a repost"
    )
    first_seen_at: datetime | None = None
    sold_at: datetime | None = None


class PriceObservation(BaseModel):
    """One verified or asking price point for an account fingerprint."""
    model_config = ConfigDict(extra="allow")

    listing: Listing
    price_egp: float | None = None
    price_usd: float | None = None
    kind: str = Field("asking", pattern="^(asking|negotiated|sold|appraised)$")
    observed_at: datetime = Field(default_factory=datetime.utcnow)


class AccountInventory(BaseModel):
    """Aggregated account attributes shared by parser output and training rows."""
    account_level: int | None = None
    collection_level: float | None = None
    mythics_count: int | None = None
    guns_count: int | None = None
    xsuits_count: int | None = None
    cars_total: int | None = None
    cars_mythic: int | None = None
    canonical_items: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """Normalized response contract for any pricing surface (API / bot / CLI)."""
    fair_value_egp: float
    lower_bound_egp: float | None = None
    upper_bound_egp: float | None = None
    segment: str = "General"
    confidence_score: int = Field(85, ge=0, le=100)
    verdict: DealVerdict = DealVerdict.UNPRICED
    explanation: str | None = None
    models_breakdown: dict[str, float] = Field(default_factory=dict)
    rules_applied: list[str] = Field(
        default_factory=list,
        description="IDs of pricing rules that fired (premiums/caps)",
    )
