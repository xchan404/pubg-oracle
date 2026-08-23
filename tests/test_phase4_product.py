"""
Phase 4/5 tests: portfolio math, deals hub, rules validation, API surfaces.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


class TestPortfolioMath:
    def test_open_and_closed_positions(self):
        from intelligence.portfolio import build_portfolio_summary

        positions = [
            {"chat_id": 1, "message_id": 10, "asked_price": 3000, "sold_price": 4200,
             "segment": "s", "timestamp": "2026-01-01"},
            {"chat_id": 1, "message_id": 11, "asked_price": 5000, "sold_price": 4500,
             "segment": "s", "timestamp": "2026-01-02"},
            {"chat_id": 1, "message_id": 12, "asked_price": 2000, "sold_price": None,
             "segment": "s2", "timestamp": "2026-01-03"},
            {"chat_id": 1, "message_id": 13, "asked_price": None, "sold_price": None,
             "segment": "s3", "timestamp": "2026-01-04"},  # no cost recorded
        ]
        out = build_portfolio_summary(positions)
        t = out["totals"]
        assert t["positions_total"] == 4
        assert t["closed_positions"] == 2
        assert t["open_positions"] == 2
        assert t["realized_pnl_egp"] == (4200 - 3000) + (4500 - 5000)  # 700
        assert t["win_rate_pct"] == 50.0
        assert t["capital_in_open_positions_egp"] == 2000  # None-cost excluded
        closed = [r for r in out["positions"] if r["status"] == "closed"]
        assert {r["roi_pct"] for r in closed} == {40.0, -10.0}

    def test_empty_portfolio(self):
        from intelligence.portfolio import build_portfolio_summary
        out = build_portfolio_summary([])
        assert out["totals"]["positions_total"] == 0
        assert out["totals"]["realized_pnl_egp"] == 0


class TestRulesValidation:
    def test_valid_current_yaml_passes(self):
        from ml.rules_engine import DEFAULT_RULES_PATH, validate_rules_text
        text = DEFAULT_RULES_PATH.read_text(encoding="utf-8")
        rules, errors = validate_rules_text(text)
        assert errors == []
        assert rules["caps"]["no_m4"]

    def test_broken_yaml_reports_errors(self):
        from ml.rules_engine import validate_rules_text
        _, errors = validate_rules_text("rare_premiums: [unclosed")
        assert any("YAML" in e for e in errors)

    def test_missing_sections_rejected(self):
        from ml.rules_engine import validate_rules_text
        _, errors = validate_rules_text("version: 9\n")
        assert any("Missing required section" in e for e in errors)


@pytest.fixture()
def client(monkeypatch):
    # Keep the hot-reload endpoint away from the real config file in tests
    import api.main as api_main
    monkeypatch.setattr(api_main, "_write_rules",
                        lambda path, text: None)
    return TestClient(api_main.app)


class TestApiPhase4:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_internal_deal_push_requires_token(self, monkeypatch, client):
        monkeypatch.setenv("INTERNAL_TOKEN", "sekrit")
        r = client.post("/internal/deal", json={
            "fair_value": 5000, "chat_title": "t",
        })
        assert r.status_code == 401

    def test_internal_deal_push_accepts_and_broadcasts(self, monkeypatch, client):
        monkeypatch.setenv("INTERNAL_TOKEN", "sekrit")
        r = client.post("/internal/deal", json={
            "fair_value": 5000, "asked_price": 3000,
            "chat_title": "unit-test", "profit": 100,
        }, headers={"X-Internal-Token": "sekrit"})
        assert r.status_code == 200
        recent = client.get("/deals/recent").json()["deals"]
        assert any(d.get("chat_title") == "unit-test" for d in recent)

    def test_recent_deals_endpoint(self, client):
        r = client.get("/deals/recent?limit=5")
        assert r.status_code == 200
        assert isinstance(r.json()["deals"], list)

    def test_rules_get(self, client):
        r = client.get("/rules")
        assert r.status_code == 200
        body = r.json()
        assert body["validation_errors"] == []
        assert "blend" in body["rules"]

    def test_rules_put_invalid_rejected_without_write(self, client):
        r = client.put("/rules", json={"yaml_text": "just_a_key: 1\n"})
        assert r.status_code == 422
        assert "Missing required section" in str(r.json()["detail"])

    def test_portfolio_endpoint_shape(self, client):
        r = client.get("/portfolio/summary")
        assert r.status_code == 200
        body = r.json()
        assert set(body) >= {"positions", "totals"}

    def test_websocket_deals_stream(self, client):
        with client.websocket_connect("/ws/deals") as ws:
            # replay buffer may be empty; connection must stay open
            assert ws is not None
