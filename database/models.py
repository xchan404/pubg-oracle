from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

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


class SnipedAd(Base):
    """A deal candidate detected by the sniper bot (unified ads table)."""
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False)
    message_id = Column(Integer, nullable=False)
    raw_text = Column(Text)
    asked_price = Column(Float, nullable=True)
    fair_value = Column(Float)
    profit = Column(Float, nullable=True)
    segment = Column(String(255))
    parsed_data = Column(Text)  # JSON dump of parsed features
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", name="uq_ads_chat_message"),
    )


class DealFeedback(Base):
    """
    Human label on a sniped ad (Phase 3 feedback flywheel).
    One row per (ad, label type). Verified sale prices feed retraining.
    """
    __tablename__ = "deal_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False, index=True)
    message_id = Column(Integer, nullable=False, index=True)
    # bought | sold_price | not_a_deal | wrong_parse | scam
    label = Column(String(32), nullable=False)
    value_egp = Column(Float, nullable=True)      # actual sale price when known
    corrected_data = Column(Text, nullable=True)  # JSON corrections for wrong_parse
    fingerprint = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", "label", name="uq_feedback_ad_label"),
    )
