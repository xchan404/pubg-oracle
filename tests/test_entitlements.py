"""
Week 3 monetization tests: plans, limits, credits, payments, partner share.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, User
from services.entitlements import (
    active_subscription,
    expire_stale_subscriptions,
    expiring_soon,
    get_entitlement,
    grant_subscription,
)
from services.payments import (
    PARTNER_SHARE_RATE,
    approve_payment,
    create_payment,
    partner_payouts,
    reject_payment,
)
from services.usage import add_credits, checks_used, consume_check, credit_balance

NOW = datetime(2026, 11, 14, 12, 0, 0)


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


def make_user(session, telegram_id=1001, **kwargs):
    user = User(telegram_id=telegram_id, **kwargs)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestEntitlements:
    def test_new_user_is_free(self, session):
        user = make_user(session)
        ent = get_entitlement(session, user, NOW)
        assert ent.plan == "free"
        assert ent.is_paid is False
        assert ent.checks_per_day == 3
        assert ent.has("delayed_deals")
        assert not ent.has("realtime_alerts")

    def test_grant_pro_activates_plan(self, session):
        user = make_user(session)
        sub = grant_subscription(session, user, "pro_monthly", days=30, now=NOW)

        ent = get_entitlement(session, user, NOW)
        assert ent.plan == "pro_monthly"
        assert ent.is_paid is True
        assert ent.checks_per_day is None
        assert ent.has("realtime_alerts")
        assert ent.subscription_id == sub.id
        assert sub.expires_at == NOW + timedelta(days=30)

    def test_renewal_extends_instead_of_resetting(self, session):
        user = make_user(session)
        first = grant_subscription(session, user, "pro_monthly", days=30, now=NOW)
        second = grant_subscription(session, user, "pro_monthly", days=30, now=NOW)

        assert first.expires_at == NOW + timedelta(days=30)
        assert second.expires_at == NOW + timedelta(days=60)

    def test_expired_subscription_falls_back_to_free(self, session):
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        assert get_entitlement(session, user, NOW).plan == "pro_monthly"
        later = NOW + timedelta(days=2)
        assert get_entitlement(session, user, later).plan == "free"

    def test_expire_stale_subscriptions(self, session):
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        assert expire_stale_subscriptions(session, NOW + timedelta(days=2)) == 1
        assert active_subscription(session, user.id, NOW + timedelta(days=2)) is None

    def test_expiring_soon_window(self, session):
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=2, now=NOW)

        assert len(expiring_soon(session, within_days=3, now=NOW)) == 1
        assert len(expiring_soon(session, within_days=1, now=NOW)) == 0

    def test_unknown_plan_rejected(self, session):
        user = make_user(session)
        with pytest.raises(ValueError):
            grant_subscription(session, user, "platinum", days=30, now=NOW)

    def test_business_plan_features(self, session):
        user = make_user(session)
        grant_subscription(session, user, "business", days=30, now=NOW)

        ent = get_entitlement(session, user, NOW)
        assert ent.has("bulk_export")
        assert ent.has("api_access")
        assert ent.has("seats_5")


class TestUsage:
    def test_free_plan_allows_three_checks(self, session):
        user = make_user(session)

        decisions = [consume_check(session, user, now=NOW) for _ in range(3)]
        assert [d.allowed for d in decisions] == [True, True, True]
        assert [d.remaining for d in decisions] == [2, 1, 0]
        assert all(d.reason == "ok" for d in decisions)

        blocked = consume_check(session, user, now=NOW)
        assert blocked.allowed is False
        assert blocked.reason == "limit_reached"

    def test_window_rolls_after_24h(self, session):
        user = make_user(session)
        for _ in range(3):
            consume_check(session, user, now=NOW)

        assert consume_check(session, user, now=NOW).allowed is False
        tomorrow = NOW + timedelta(hours=25)
        assert consume_check(session, user, now=tomorrow).allowed is True

    def test_pro_is_unlimited(self, session):
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=30, now=NOW)

        for _ in range(50):
            decision = consume_check(session, user, now=NOW)
            assert decision.allowed is True
            assert decision.reason == "unlimited"
            assert decision.remaining is None

    def test_credit_fallback_after_limit(self, session):
        user = make_user(session)
        add_credits(session, user.id, 2, "purchase", now=NOW)

        for _ in range(3):
            assert consume_check(session, user, now=NOW).allowed is True

        paid = consume_check(session, user, now=NOW)
        assert paid.allowed is True
        assert paid.used_credit is True
        assert paid.reason == "credit"
        assert credit_balance(session, user.id) == 1

        second = consume_check(session, user, now=NOW)
        assert second.allowed is True
        assert credit_balance(session, user.id) == 0

        assert consume_check(session, user, now=NOW).allowed is False

    def test_banned_user_is_denied(self, session):
        user = make_user(session, is_banned=True)
        decision = consume_check(session, user, now=NOW)
        assert decision.allowed is False
        assert decision.reason == "banned"

    def test_unmetered_kinds_are_free(self, session):
        user = make_user(session)
        for _ in range(10):
            assert consume_check(session, user, kind="alert", now=NOW).allowed is True
        # alert usage must not eat the free check quota
        assert checks_used(session, user.id, NOW) == 0
        assert consume_check(session, user, now=NOW).allowed is True

    def test_credits_cannot_go_negative(self, session):
        user = make_user(session)
        with pytest.raises(ValueError):
            add_credits(session, user.id, -1, "refund", now=NOW)


class TestPayments:
    def test_create_payment_defaults_to_pending(self, session):
        user = make_user(session, currency="EGP")
        payment = create_payment(
            session, user, provider="vodafone_cash", amount=299, external_ref="VF-1"
        )
        assert payment.status == "pending"
        assert payment.currency == "EGP"
        assert payment.partner_share_amount is None

    def test_rejects_bad_provider_and_amount(self, session):
        user = make_user(session)
        with pytest.raises(ValueError):
            create_payment(session, user, provider="bitcoin", amount=100)
        with pytest.raises(ValueError):
            create_payment(session, user, provider="manual", amount=0)

    def test_approval_grants_pro_and_partner_share(self, session):
        user = make_user(session, referred_by="chan_alpha")
        payment = create_payment(
            session, user, provider="vodafone_cash", amount=299, external_ref="VF-2"
        )

        approve_payment(session, payment, plan="pro_monthly", days=30,
                        reviewed_by="owner", now=NOW)

        assert payment.status == "approved"
        assert payment.reviewed_by == "owner"
        assert payment.partner_code == "chan_alpha"
        assert payment.partner_share_amount == round(299 * PARTNER_SHARE_RATE, 2)
        assert get_entitlement(session, user, NOW).plan == "pro_monthly"

    def test_approval_with_credits(self, session):
        user = make_user(session)
        payment = create_payment(session, user, provider="instapay", amount=15)

        approve_payment(session, payment, credits=1, now=NOW)
        assert credit_balance(session, user.id) == 1

    def test_approval_is_idempotent(self, session):
        user = make_user(session)
        payment = create_payment(session, user, provider="manual", amount=299)

        approve_payment(session, payment, plan="pro_monthly", days=30, now=NOW)
        first_expiry = active_subscription(session, user.id, NOW).expires_at

        approve_payment(session, payment, plan="pro_monthly", days=30, now=NOW)
        assert active_subscription(session, user.id, NOW).expires_at == first_expiry

    def test_rejected_payment_cannot_be_approved(self, session):
        user = make_user(session)
        payment = create_payment(session, user, provider="manual", amount=299)

        reject_payment(session, payment, reviewed_by="owner", reason="no proof", now=NOW)
        assert payment.status == "rejected"
        with pytest.raises(ValueError):
            approve_payment(session, payment, plan="pro_monthly", days=30, now=NOW)

    def test_approval_auto_grants_from_offer(self, session):
        user = make_user(session)
        payment = create_payment(
            session, user, provider="vodafone_cash", amount=299, offer_code="pro_monthly"
        )
        approve_payment(session, payment, now=NOW)

        assert get_entitlement(session, user, NOW).plan == "pro_monthly"
        sub = active_subscription(session, user.id, NOW)
        assert sub.expires_at == NOW + timedelta(days=30)

    def test_approval_auto_grants_credits_from_offer(self, session):
        user = make_user(session)
        payment = create_payment(
            session, user, provider="instapay", amount=75, offer_code="credits_5"
        )
        approve_payment(session, payment, now=NOW)
        assert credit_balance(session, user.id) == 5

    def test_partner_payout_report(self, session):
        user = make_user(session, referred_by="chan_alpha")
        p1 = create_payment(session, user, provider="vodafone_cash", amount=299)
        p2 = create_payment(session, user, provider="instapay", amount=15)
        approve_payment(session, p1, plan="pro_monthly", days=30, now=NOW)
        approve_payment(session, p2, credits=1, now=NOW)

        payouts = partner_payouts(session)
        assert len(payouts) == 1
        assert payouts[0].partner_code == "chan_alpha"
        assert payouts[0].gross == 314.0
        assert payouts[0].share == round(314 * PARTNER_SHARE_RATE, 2)
        assert payouts[0].payments == 2
