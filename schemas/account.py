"""
Pydantic Account Schema Definition
Enforces strict type validation and structural integrity for parsed accounts across pipeline, DB, and API.
"""

from pydantic import BaseModel, Field


class ParsedAccountSchema(BaseModel):
    clean_text: str | None = ""
    account_level: int | None = None
    collection_level: float | None = None
    mythics_count: int | None = None
    guns_count: int | None = None
    xsuits_count: int | None = None

    price_egp: float | None = None
    price_usd: float | None = None

    m4_type: str | None = None
    m4_level: int | None = None
    m4_is_max: bool | None = False

    cars_total: int | None = None
    cars_mythic: int | None = None
    has_airdrop_car: bool | None = False

    has_internal_link: bool | None = False
    has_twitter_link: bool | None = False
    is_facebook_disabled: bool | None = False
    has_trusted_middleman: bool | None = False
    linkage_type: str | None = "unknown"

    canonical_items: list[str] = Field(default_factory=list)
    extracted_items_str: str | None = ""
    active_combos_str: str | None = ""

    prestige_score: float | None = 0.0
    rarity_score: float | None = 0.0
    combo_multiplier: float | None = 1.0

    class Config:
        arbitrary_types_allowed = True
