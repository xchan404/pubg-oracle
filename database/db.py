# -*- coding: utf-8 -*-
"""
Database Manager (SQLAlchemy)
Handles connection to SQLite (or Postgres) and provides helper methods.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, RawMessage, ParsedAccount, Channel, MarketStat
from config import DB_PATH, DATABASE_URL
import logging
from datetime import datetime

logger = logging.getLogger("pubg_scraper")

# Create SQLAlchemy engine (Supports PostgreSQL or SQLite dynamically)
if DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Creates all tables based on SQLAlchemy models.
    """
    try:
        Base.metadata.create_all(bind=engine)
        
        # Also create checkpoints table using raw SQL for backwards compatibility
        # since it's only used by the scraper internally
        with engine.begin() as conn:
            conn.exec_driver_sql("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    channel_username TEXT PRIMARY KEY,
                    last_scraped_message_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        logger.info("Database initialized successfully with SQLAlchemy models.")
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

def get_db():
    """
    Dependency to get a DB session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Compatibility Layer for Scraper ---

def get_connection():
    """Returns a raw SQLite connection for old code compatibility."""
    import sqlite3
    return sqlite3.connect(DB_PATH)

def save_message(conn, msg: dict) -> bool:
    """
    Saves a raw message using SQLAlchemy.
    """
    db = SessionLocal()
    try:
        # Check if exists
        exists = db.query(RawMessage).filter(
            RawMessage.channel_username == msg["channel_username"],
            RawMessage.message_id == msg["message_id"]
        ).first()
        
        if not exists:
            new_msg = RawMessage(
                message_id=msg["message_id"],
                channel_username=msg["channel_username"],
                text=msg["text"],
                date=msg["date"],
                views=msg.get("views", 0),
                forwards=msg.get("forwards", 0),
                has_photo=msg.get("has_photo", 0),
                photo_path=msg.get("photo_path"),
                is_grouped=msg.get("is_grouped", 0),
                scraped_at=datetime.now().isoformat()
            )
            db.add(new_msg)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving message: {e}")
        return False
    finally:
        db.close()

def save_checkpoint(conn, channel_username: str, last_message_id: int):
    import sqlite3
    try:
        if not isinstance(conn, sqlite3.Connection):
            conn = get_connection()
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO checkpoints (channel_username, last_scraped_message_id, updated_at)
            VALUES (?, ?, ?)
        """, (channel_username, last_message_id, now_str))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving checkpoint: {e}")

def get_checkpoint(conn, channel_username: str) -> int:
    import sqlite3
    try:
        if not isinstance(conn, sqlite3.Connection):
            conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT last_scraped_message_id FROM checkpoints WHERE channel_username = ?
        """, (channel_username,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return 0
    except Exception as e:
        return 0
