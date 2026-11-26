from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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

    __table_args__ = (
        UniqueConstraint("channel_username", "message_id",
                         name="uq_parsed_channel_message"),
    )

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


# ─────────────────────────────────────────────────────────────
# Monetization layer (Week 3): users, subscriptions, payments,
# usage metering and credit ledger.
# ─────────────────────────────────────────────────────────────

class User(Base):
    """A Telegram user of the bot/dashboard."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(8), default="ar")
    country: Mapped[str | None] = mapped_column(String(8))   # EG | SA | AE | ...
    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    referred_by: Mapped[str | None] = mapped_column(String(64), index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    """A paid (or granted) entitlement period for a user."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)       # pro_monthly | pro_annual | business
    status: Mapped[str] = mapped_column(String(16), default="active")   # active | expired | cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    price_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    external_ref: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Payment(Base):
    """Money in, with manual approval for wallets and Stars reconciliation."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    external_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    proof_note: Mapped[str | None] = mapped_column(Text)
    offer_code: Mapped[str | None] = mapped_column(String(32), index=True)
    partner_code: Mapped[str | None] = mapped_column(String(64), index=True)
    partner_share_amount: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[str | None] = mapped_column(String(64))


class UsageEvent(Base):
    """One row per metered action (check, alert, valuation)."""
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), default="check", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    meta: Mapped[str | None] = mapped_column(Text)


class CreditLedger(Base):
    """Append-only credit balance. Balance = SUM(delta)."""
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
