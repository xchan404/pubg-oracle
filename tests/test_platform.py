"""Knowledge base YAML integrity + domain schema + unified ads store tests."""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pydantic import ValidationError

from ml.features import LEGENDARY_COMBOS
from parser.aliases import KNOWLEDGE_BASE, resolve_alias, resolve_text_items
from schemas.domain import AccountInventory, DealVerdict, EvaluationResult, Listing, Seller


class TestKnowledgeBaseYAML:
    def test_items_loaded(self):
        assert len(KNOWLEDGE_BASE) >= 30
        assert "glacier_m416" in KNOWLEDGE_BASE
        assert "xsuit_pharaoh" in KNOWLEDGE_BASE

    def test_item_shape(self):
        for item_id, data in KNOWLEDGE_BASE.items():
            assert isinstance(data["aliases"], list) and data["aliases"], item_id
            assert isinstance(data["prestige_score"], (int, float))
            assert isinstance(data["market_score"], (int, float))

    def test_combos_loaded(self):
        assert "triple_threat" in LEGENDARY_COMBOS
        assert LEGENDARY_COMBOS["triple_threat"]["multiplier"] == 2.0

    def test_resolution_still_works_after_yaml_migration(self):
        assert resolve_alias("جليشر") == "glacier_m416"
        assert resolve_alias("فرعون") == "xsuit_pharaoh"
        items = resolve_text_items("حساب فيه جليشر وموميا بيضا")
        assert "glacier_m416" in items and "mummy_white" in items


class TestDomainSchemas:
    def test_listing_roundtrip(self):
        listing = Listing(channel_username="test_channel", message_id=42, raw_text="hello")
        assert listing.views == 0
        assert listing.fingerprint is None

    def test_listing_requires_fields(self):
        with pytest.raises(ValidationError):
            Listing(message_id=1)

    def test_evaluation_result_defaults(self):
        res = EvaluationResult(fair_value_egp=1234.5)
        assert res.verdict == DealVerdict.UNPRICED
        assert 0 <= res.confidence_score <= 100

    def test_seller_and_inventory(self):
        seller = Seller(display_name="flipper", trust_score=88.0)
        inv = AccountInventory(mythics_count=50, canonical_items=["glacier_m416"])
        assert seller.trust_score > 50
        assert inv.canonical_items == ["glacier_m416"]


class TestUnifiedAdsStore:
    @pytest.fixture()
    def ads_env(self, tmp_path, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        import database.ads as ads
        from database.models import Base

        engine = create_engine(f"sqlite:///{tmp_path / 'unified.db'}")
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        monkeypatch.setattr(ads, "SessionLocal", TestSession)

        legacy_path = tmp_path / "sniper.db"
        conn = sqlite3.connect(legacy_path)
        conn.execute(
            "CREATE TABLE ads (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, "
            "message_id INTEGER, raw_text TEXT, asked_price REAL, fair_value REAL, "
            "profit REAL, segment TEXT, parsed_data TEXT, timestamp DATETIME)"
        )
        conn.execute(
            "INSERT INTO ads (chat_id, message_id, raw_text, asked_price, fair_value, profit, segment, parsed_data, timestamp) "
            "VALUES (-100, 7, 'ad text', 2000, 3000, 1000, 'seg', '{}', '2026-01-01T10:00:00')"
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(ads, "LEGACY_SNIPER_DB", legacy_path)
        return ads, tmp_path

    def test_save_ad_new_then_duplicate(self, ads_env):
        ads, _ = ads_env
        kwargs = dict(raw_text="t", asked_price=100.0, fair_value=200.0,
                      profit=100.0, segment="s", parsed_data={"a": 1})
        assert ads.save_ad(chat_id=1, message_id=1, **kwargs) is True
        assert ads.save_ad(chat_id=1, message_id=1, **kwargs) is False

    def test_legacy_migration_moves_rows_and_file(self, ads_env):
        ads, tmp_path = ads_env
        migrated = ads.migrate_legacy_sniper_db()
        assert migrated == 1
        assert not ads.LEGACY_SNIPER_DB.exists()
        assert (tmp_path / "sniper.migrated").exists()

    def test_migration_idempotent(self, ads_env):
        ads, _ = ads_env
        assert ads.migrate_legacy_sniper_db() == 1
        # legacy file renamed; second call finds nothing
        assert ads.migrate_legacy_sniper_db() == 0
