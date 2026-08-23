# -*- coding: utf-8 -*-
"""
Pydantic Account Schema Definition
Enforces strict type validation and structural integrity for parsed accounts across pipeline, DB, and API.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class ParsedAccountSchema(BaseModel):
    clean_text: Optional[str] = ""
    account_level: Optional[int] = None
    collection_level: Optional[float] = None
    mythics_count: Optional[int] = None
    guns_count: Optional[int] = None
    xsuits_count: Optional[int] = None
    
    price_egp: Optional[float] = None
    price_usd: Optional[float] = None
    
    m4_type: Optional[str] = None
    m4_level: Optional[int] = None
    m4_is_max: Optional[bool] = False
    
    cars_total: Optional[int] = None
    cars_mythic: Optional[int] = None
    has_airdrop_car: Optional[bool] = False
    
    has_internal_link: Optional[bool] = False
    has_twitter_link: Optional[bool] = False
    is_facebook_disabled: Optional[bool] = False
    has_trusted_middleman: Optional[bool] = False
    linkage_type: Optional[str] = "unknown"
    
    canonical_items: List[str] = Field(default_factory=list)
    extracted_items_str: Optional[str] = ""
    active_combos_str: Optional[str] = ""
    
    prestige_score: Optional[float] = 0.0
    rarity_score: Optional[float] = 0.0
    combo_multiplier: Optional[float] = 1.0
    
    class Config:
        arbitrary_types_allowed = True
