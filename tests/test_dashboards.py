"""
Dashboard API tests (user + admin).

Covers the two things that must never drift: Telegram WebApp `initData`
verification, and admin authorisation on every mutating route.
"""

import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dashboards import router as dashboards_router
from api.dashboards import verify_telegram_init_data
from database.db import get_db
from database.models import Base, Payment, User
from services.payments import create_payment

BOT_TOKEN = "123456:test-bot-token"
ADMIN_TOKEN = "test-admin-token"


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def client(session, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("ADMIN_DASHBOARD_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("MY_CHAT_ID", "999000111")

    app = FastAPI()
    app.include_router(dashboards_router)
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def sign_init_data(user: dict, bot_token: str = BOT_TOKEN, auth_date: int | None = None) -> str:
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAExampleQueryId",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def admin_headers(token: str = ADMIN_TOKEN) -> dict:
    return {"X-Admin-Token": token}


def make_user(session, telegram_id: int = 5001, **kwargs) -> User:
    user = User(telegram_id=telegram_id, **kwargs)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ─── initData verification ───────────────────────────────────────────────────

class TestInitData:
    def test_valid_payload_returns_user(self):
        payload = sign_init_data({"id": 777, "username": "flipper", "first_name": "Ali"})
        user = verify_telegram_init_data(payload, BOT_TOKEN)
        assert user is not None
        assert user["id"] == 777
        assert user["username"] == "flipper"

    def test_wrong_bot_token_is_rejected(self):
        payload = sign_init_data({"id": 777}, bot_token="other-token")
        assert verify_telegram_init_data(payload, BOT_TOKEN) is None

    def test_tampered_field_is_rejected(self):
        payload = sign_init_data({"id": 777})
        tampered = payload.replace("AAExampleQueryId", "AAHijackedQueryId")
        assert verify_telegram_init_data(tampered, BOT_TOKEN) is None

    def test_expired_payload_is_rejected(self):
        old = int(time.time()) - (25 * 60 * 60)
        payload = sign_init_data({"id": 777}, auth_date=old)
        assert verify_telegram_init_data(payload, BOT_TOKEN) is None

    def test_missing_hash_is_rejected(self):
        assert verify_telegram_init_data("auth_date=1&user=%7B%7D", BOT_TOKEN) is None

    def test_empty_inputs_are_rejected(self):
        assert verify_telegram_init_data("", BOT_TOKEN) is None
        assert verify_telegram_init_data("hash=abc", "") is None


# ─── Public config ───────────────────────────────────────────────────────────

class TestConfig:
    def test_config_lists_markets_and_is_public(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        body = response.json()
        codes = {item["code"] for item in body["countries"]}
        assert {"EG", "SA", "AE"} <= codes
        assert "token" not in json.dumps(body).lower()


# ─── User dashboard ──────────────────────────────────────────────────────────

class TestUserDashboard:
    def test_me_requires_identity(self, client):
        assert client.get("/api/me").status_code == 401

    def test_me_creates_user_from_init_data(self, client, session):
        payload = sign_init_data({"id": 4242, "username": "buyer", "first_name": "Mona"})
        response = client.get("/api/me", headers={"X-Telegram-Init-Data": payload})
        assert response.status_code == 200

        body = response.json()
        assert body["user"]["telegram_id"] == 4242
        assert body["user"]["username"] == "buyer"
        assert body["plan"]["code"] == "free"
        assert body["usage"]["limit"] == 3
        assert body["usage"]["used_24h"] == 0
        assert body["credits"] == 0
        assert body["payments"] == []
        assert any(offer["code"] == "pro_monthly" for offer in body["offers"])

        # The row is real, not a stub.
        assert session.query(User).filter_by(telegram_id=4242).count() == 1

    def test_offers_follow_market_currency(self, client):
        payload = sign_init_data({"id": 4243})
        headers = {"X-Telegram-Init-Data": payload}
        assert client.get("/api/me", headers=headers).status_code == 200

        response = client.post("/api/me/locale", json={"country": "SA"}, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"country": "SA", "currency": "SAR"}

        offers = client.get("/api/me", headers=headers).json()["offers"]
        pro = next(offer for offer in offers if offer["code"] == "pro_monthly")
        assert pro["currency"] == "SAR"
        assert pro["price"] == 79.0

    def test_unsupported_country_is_rejected(self, client):
        payload = sign_init_data({"id": 4244})
        response = client.post(
            "/api/me/locale",
            json={"country": "FR"},
            headers={"X-Telegram-Init-Data": payload},
        )
        assert response.status_code == 400


# ─── Admin auth ──────────────────────────────────────────────────────────────

class TestAdminAuth:
    @pytest.mark.parametrize("path", [
        "/api/admin/session",
        "/api/admin/overview",
        "/api/admin/users",
        "/api/admin/payments",
        "/api/admin/partners",
        "/api/admin/data",
    ])
    def test_admin_routes_reject_anonymous(self, client, path):
        assert client.get(path).status_code == 401

    def test_admin_routes_reject_bad_token(self, client):
        assert client.get("/api/admin/overview", headers=admin_headers("nope")).status_code == 401

    def test_session_accepts_valid_token(self, client):
        response = client.get("/api/admin/session", headers=admin_headers())
        assert response.status_code == 200
        assert response.json()["role"] == "token"

    def test_owner_telegram_login_is_accepted(self, client, monkeypatch):
        payload = sign_init_data({"id": 999000111})
        response = client.get("/api/admin/session", headers={"X-Telegram-Init-Data": payload})
        assert response.status_code == 200
        assert response.json()["role"] == "telegram_owner"

    def test_non_owner_telegram_login_is_rejected(self, client):
        payload = sign_init_data({"id": 123456})
        response = client.get("/api/admin/session", headers={"X-Telegram-Init-Data": payload})
        assert response.status_code == 401

    def test_mutations_require_admin(self, client):
        assert client.post("/api/admin/payments/1/approve").status_code == 401
        assert client.post("/api/admin/users/1/grant", json={"plan": "pro_monthly"}).status_code == 401
        assert client.post("/api/admin/users/1/credits", json={"amount": 5}).status_code == 401
        assert client.post("/api/admin/users/1/ban", json={"banned": True}).status_code == 401
        assert client.post("/api/admin/retrain").status_code == 401


# ─── Admin operations ────────────────────────────────────────────────────────

class TestAdminOperations:
    def test_overview_reports_empty_state_honestly(self, client):
        body = client.get("/api/admin/overview", headers=admin_headers()).json()
        assert body["users"]["total"] == 0
        assert body["payments"]["pending"] == 0
        assert body["revenue_month"] == []
        assert body["revenue_lifetime"] == []
        assert "freshness" in body

    def test_payment_approval_grants_subscription(self, client, session):
        user = make_user(session, telegram_id=6001, first_name="Buyer")
        payment = create_payment(
            session, user,
            provider="vodafone_cash",
            amount=299.0,
            currency="EGP",
            offer_code="pro_monthly",
        )

        response = client.post(
            f"/api/admin/payments/{payment.id}/approve",
            json={},
            headers=admin_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["reviewed_by"] == "admin:token"

        me = client.get("/api/admin/users", headers=admin_headers()).json()
        assert me["items"][0]["plan"]["code"] == "pro_monthly"
        assert me["items"][0]["plan"]["is_paid"] is True

    def test_payment_rejection_does_not_grant(self, client, session):
        user = make_user(session, telegram_id=6002)
        payment = create_payment(
            session, user,
            provider="instapay",
            amount=299.0,
            currency="EGP",
            offer_code="pro_monthly",
        )

        response = client.post(
            f"/api/admin/payments/{payment.id}/reject",
            json={"reason": "no transfer received"},
            headers=admin_headers(),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        refreshed = session.get(Payment, payment.id)
        assert refreshed.status == "rejected"
        assert "no transfer received" in (refreshed.proof_note or "")

    def test_credit_pack_approval_adds_credits(self, client, session):
        user = make_user(session, telegram_id=6003)
        payment = create_payment(
            session, user,
            provider="manual",
            amount=75.0,
            currency="EGP",
            offer_code="credits_5",
        )

        response = client.post(
            f"/api/admin/payments/{payment.id}/approve",
            json={},
            headers=admin_headers(),
        )
        assert response.status_code == 200

        me = client.get("/api/me", headers={"X-Telegram-Init-Data": sign_init_data({"id": 6003})})
        assert me.status_code == 200
        assert me.json()["credits"] == 5

    def test_grant_and_credits_and_ban(self, client, session):
        user = make_user(session, telegram_id=6004)
        headers = admin_headers()

        granted = client.post(
            f"/api/admin/users/{user.id}/grant",
            json={"plan": "business", "days": 30},
            headers=headers,
        )
        assert granted.status_code == 200
        assert granted.json()["plan"]["code"] == "business"

        credits = client.post(
            f"/api/admin/users/{user.id}/credits",
            json={"amount": 7, "reason": "goodwill"},
            headers=headers,
        )
        assert credits.status_code == 200
        assert credits.json()["credits"] == 7

        banned = client.post(
            f"/api/admin/users/{user.id}/ban",
            json={"banned": True},
            headers=headers,
        )
        assert banned.status_code == 200
        assert banned.json()["is_banned"] is True

        unbanned = client.post(
            f"/api/admin/users/{user.id}/ban",
            json={"banned": False},
            headers=headers,
        )
        assert unbanned.json()["is_banned"] is False

    def test_user_search_matches_username(self, client, session):
        make_user(session, telegram_id=6005, username="dealshunter")
        make_user(session, telegram_id=6006, username="someoneelse")

        body = client.get(
            "/api/admin/users?query=dealshunter", headers=admin_headers()
        ).json()
        assert len(body["items"]) == 1
        assert body["items"][0]["username"] == "dealshunter"

    def test_partners_report_sums_approved_only(self, client, session):
        user = make_user(session, telegram_id=6007, referred_by="partner_a")
        approved = create_payment(
            session, user,
            provider="vodafone_cash", amount=299.0, currency="EGP",
            offer_code="pro_monthly", partner_code="partner_a",
        )
        create_payment(
            session, user,
            provider="vodafone_cash", amount=299.0, currency="EGP",
            offer_code="pro_monthly", partner_code="partner_a",
        )

        client.post(
            f"/api/admin/payments/{approved.id}/approve", json={}, headers=admin_headers()
        )

        body = client.get("/api/admin/partners", headers=admin_headers()).json()
        assert len(body["items"]) == 1
        partner = body["items"][0]
        assert partner["code"] == "partner_a"
        assert partner["gross"] == 299.0
        assert partner["share"] == round(299.0 * 0.25, 2)
        assert partner["payments"] == 1

    def test_unknown_payment_returns_404(self, client):
        response = client.post(
            "/api/admin/payments/999999/approve", json={}, headers=admin_headers()
        )
        assert response.status_code == 404
