import sqlite3
import os
import json
from typing import Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), 'sniper.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            message_id INTEGER,
            raw_text TEXT,
            asked_price REAL,
            fair_value REAL,
            profit REAL,
            segment TEXT,
            parsed_data TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, message_id)
        )
    ''')
    conn.commit()
    conn.close()

def save_ad(chat_id: int, message_id: int, raw_text: str, asked_price: Optional[float],
            fair_value: float, profit: Optional[float], segment: str, parsed_data: Dict[str, Any]):
    """Save ad to DB. Returns True if successfully saved (new ad), False if it already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ads (chat_id, message_id, raw_text, asked_price, fair_value, profit, segment, parsed_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (chat_id, message_id, raw_text, asked_price, fair_value, profit, segment, json.dumps(parsed_data, ensure_ascii=False)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Already exists (UNIQUE constraint on chat_id, message_id)
        return False
    finally:
        conn.close()

# Initialize DB on import
init_db()
