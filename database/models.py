# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    type = Column(String(50), default="public")
    last_scraped = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class RawMessage(Base):
    __tablename__ = "raw_messages"
    
    channel_username = Column(String(255), primary_key=True)
    message_id = Column(Integer, primary_key=True)
    date = Column(String)  # Stored as string in SQLite
    text = Column(Text)
    views = Column(Integer, default=0)
    forwards = Column(Integer, default=0)
    has_photo = Column(Integer, default=0)
    photo_path = Column(Text)
    is_grouped = Column(Integer, default=0)
    scraped_at = Column(String)

class ParsedAccount(Base):
    __tablename__ = "parsed_accounts"
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, index=True)
    channel_username = Column(String(255))
    
    price_egp = Column(Float, nullable=True)
    price_usd = Column(Float, nullable=True)
    
    account_level = Column(Integer, nullable=True)
    mythics_count = Column(Integer, nullable=True)
    
    # Engine Features
    prestige_score = Column(Float, default=0.0)
    rarity_score = Column(Float, default=0.0)
    combo_multiplier = Column(Float, default=1.0)
    final_market_score = Column(Float, default=0.0)
    
    # JSON for active combos and raw items could be stored here, 
    # but string representation is easier for SQLite
    active_combos_str = Column(Text, nullable=True)
    extracted_items_str = Column(Text, nullable=True)

class MarketStat(Base):
    __tablename__ = "market_stats"
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    item_id = Column(String(255), index=True)
    average_price_egp = Column(Float)
    demand_score = Column(Float)
    sales_volume = Column(Integer)
