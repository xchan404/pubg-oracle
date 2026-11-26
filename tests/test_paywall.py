"""
Week 3 paywall tests: onboarding, referral, quota, manual payment intents.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from bot import paywall
from database.models import Base, Payment
from services.entitlements import get_entitlement


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


class TestStartPayload:
    @pytest.mark.parametrize("text,expected", [
        ("/start", None),
        ("/start partner_chan_alpha", "chan_alpha"),
        ("/start partner_", None),
        ("/start random_code", "random_code"),
        ("  /start   partner_xyz  ", "xyz"),
    ])
    def test_parse(self, text, expected):
        assert paywall.parse_start_payload(text) == expected


class TestTexts:
    def test_welcome_escapes_name(self):
        text = paywall.welcome_text("<b>Ali</b>")
        assert "&lt;b&gt;Ali&lt;/b&gt;" in text
        assert "/plans" in text

    def test_plans_show_both_markets(self):
        egp = paywall.plans_text("EGP")
        sar = paywall.plans_text("SAR")
        assert "299" in egp and "EGP" in egp
        assert "79" in sar and "SAR" in sar

    def test_payment_instructions_include_amount(self):
        text = paywall.payment_instructions_text("pro_monthly", "EGP")
        assert "299" in text
        assert "فودافون كاش" in text

    def test_quota_text_offers_upgrade(self):
        text = paywall.quota_exceeded_text("EGP")
        assert "/plans" in text
        assert "Pro" in text


class TestOnboarding:
    def test_start_creates_user_and_applies_referral(self, session):
        user, applied = paywall.start_user(
            session, 555, username="ali", first_name="Ali",
            payload="/start partner_chan_alpha",
        )
        assert applied == "chan_alpha"
        assert user.referred_by == "chan_alpha"
        assert user.username == "ali"

    def test_referral_is_first_wins(self, session):
        paywall.start_user(session, 556, payload="/start partner_first")
        user, applied = paywall.start_user(session, 556, payload="/start partner_second")
        assert applied is None
        assert user.referred_by == "first"

    def test_country_sets_currency(self, session):
        user, _ = paywall.start_user(session, 557)
        assert paywall.set_country(session, user, "sa") == "SAR"
        assert user.currency == "SAR"
        assert paywall.set_country(session, user, "zz") is None


class TestAccessGate:
    def test_free_three_then_blocked(self, session):
        results = [paywall.check_access(session, 600) for _ in range(3)]
        assert all(r.allowed for r in results)
        assert results[-1].remaining == 0

        blocked = paywall.check_access(session, 600)
        assert blocked.allowed is False
        assert blocked.reason == "limit_reached"
        assert blocked.plan == "free"

    def test_pro_is_unlimited(self, session):
        from services.entitlements import grant_subscription

        user, _ = paywall.start_user(session, 601)
        grant_subscription(session, user, "pro_monthly", days=30)

        for _ in range(10):
            assert paywall.check_access(session, 601).allowed is True


class TestPaymentTexts:
    def test_activation_for_plan_shows_expiry(self):
        from datetime import datetime

        text = paywall.activation_text(
            "pro_monthly", datetime(2026, 12, 14, 10, 0), 0, "EGP"
        )
        assert "pro_monthly" in text
        assert "2026-12-14" in text
        assert "غير محدودة" in text

    def test_activation_for_credits_only(self):
        text = paywall.activation_text("free", None, 5, "EGP")
        assert "5" in text
        assert "الكريدت" in text

    def test_payment_request_card_escapes_username(self):
        text = paywall.payment_request_text(
            12, 555, "<bad>", "Pro شهري", 299.0, "EGP", "VF-1234"
        )
        assert "#12" in text
        assert "&lt;bad&gt;" in text
        assert "299" in text
        assert "VF-1234" in text

    def test_payment_request_without_proof(self):
        text = paywall.payment_request_text(
            13, 556, None, "Pro شهري", 79.0, "SAR", None
        )
        assert "الإثبات" not in text
        assert "79" in text


class TestWalletIntent:
    def test_creates_pending_payment_with_offer(self, session):
        user, _ = paywall.start_user(session, 700)
        payment, offer, amount = paywall.create_wallet_intent(
            session, user, "pro_monthly", currency="EGP",
            proof_note="VF-123456",
        )
        assert isinstance(payment, Payment)
        assert payment.status == "pending"
        assert payment.offer_code == "pro_monthly"
        assert payment.provider == "vodafone_cash"
        assert amount == 299.0
        assert payment.currency == "EGP"
        assert payment.partner_code is None

    def test_uses_user_currency_and_partner(self, session):
        user, _ = paywall.start_user(session, 701, payload="/start partner_chan")
        paywall.set_country(session, user, "ae")
        payment, offer, amount = paywall.create_wallet_intent(session, user, "pro_monthly")
        assert payment.currency == "AED"
        assert amount == 79.0
        assert payment.partner_code == "chan"

    def test_unknown_offer_rejected(self, session):
        user, _ = paywall.start_user(session, 702)
        with pytest.raises(ValueError):
            paywall.create_wallet_intent(session, user, "platinum")

    def test_summary_shows_plan_and_credits(self, session):
        user, _ = paywall.start_user(session, 703)
        text = paywall.user_summary_text(session, user)
        assert "free" in text
        assert "الكريدت" in text
        assert get_entitlement(session, user).plan == "free"
