"""
Week 3 lifecycle tests: expiry notices, renewal reminders, daily digest, gate.

The notifier's HTTP transport is injected, so nothing here touches Telegram.
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, User
from services.entitlements import active_subscription, get_entitlement, grant_subscription
from services.lifecycle import (
    MaintenanceReport,
    daily_digest_text,
    run_daily_if_due,
    run_daily_maintenance,
)
from services.notifier import BotNotifier
from services.payments import approve_payment, create_payment

NOW = datetime(2026, 11, 14, 9, 0, 0)


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


class Recorder:
    """Captures Bot API payloads instead of sending them."""

    def __init__(self):
        self.messages = []

    def __call__(self, url, body, timeout):
        payload = json.loads(body.decode("utf-8"))
        self.messages.append({"url": url, **payload})

    def chat_ids(self):
        return [m["chat_id"] for m in self.messages]


def enabled_notifier(recorder):
    return BotNotifier(token="TEST-TOKEN", transport=recorder)


class TestNotifier:
    def test_disabled_without_token(self, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "")
        notifier = BotNotifier()
        assert notifier.enabled is False
        assert notifier.send(1, "hi").ok is False
        assert notifier.send(1, "hi").error == "not_configured"

    def test_sends_html_payload(self):
        recorder = Recorder()
        result = enabled_notifier(recorder).send(42, "<b>hi</b>")

        assert result.ok is True
        assert recorder.messages[0]["chat_id"] == 42
        assert recorder.messages[0]["text"] == "<b>hi</b>"
        assert recorder.messages[0]["parse_mode"] == "HTML"
        assert "TEST-TOKEN" in recorder.messages[0]["url"]

    def test_transport_failure_is_soft(self):
        def boom(url, body, timeout):
            raise RuntimeError("network down")

        result = BotNotifier(token="T", transport=boom).send(1, "hi")
        assert result.ok is False
        assert "network down" in (result.error or "")


class TestDailyMaintenance:
    def test_disabled_notifier_skips_messages_but_expires(self, session, monkeypatch):
        monkeypatch.setenv("BOT_TOKEN", "")
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        report = run_daily_maintenance(session, BotNotifier(), now=NOW + timedelta(days=2))

        assert report.expired == 1
        assert report.skipped >= 1
        assert report.sent == 0
        assert report.digest_sent is False
        assert active_subscription(session, user.id, NOW + timedelta(days=2)) is None
        assert get_entitlement(session, user, NOW + timedelta(days=2)).plan == "free"

    def test_sends_expiry_notice_before_flipping_status(self, session):
        recorder = Recorder()
        user = make_user(session, first_name="Ali")
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        report = run_daily_maintenance(
            session,
            enabled_notifier(recorder),
            now=NOW + timedelta(days=2),
            owner_chat=999,
        )

        assert report.expired == 1
        assert report.sent == 1          # expiry notice (digest counted separately)
        assert report.failed == 0
        assert report.digest_sent is True
        assert recorder.chat_ids() == [user.telegram_id, 999]
        assert "انتهى اشتراكك" in recorder.messages[0]["text"]
        assert "Ali" in recorder.messages[0]["text"]

    def test_renewal_reminder_within_window(self, session):
        recorder = Recorder()
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=2, now=NOW)

        report = run_daily_maintenance(
            session, enabled_notifier(recorder), now=NOW, owner_chat=999, reminder_days=3
        )

        assert report.reminded == 1
        assert report.expired == 0
        assert "ينتهي" in recorder.messages[0]["text"]
        # still active — reminder must not remove access
        assert get_entitlement(session, user, NOW).plan == "pro_monthly"

    def test_no_reminder_outside_window(self, session):
        recorder = Recorder()
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=30, now=NOW)

        report = run_daily_maintenance(
            session, enabled_notifier(recorder), now=NOW, owner_chat=999, reminder_days=3
        )

        assert report.reminded == 0
        assert report.expired == 0
        assert recorder.chat_ids() == [999]   # digest only

    def test_banned_user_is_not_messaged(self, session):
        recorder = Recorder()
        user = make_user(session, is_banned=True)
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        report = run_daily_maintenance(
            session, enabled_notifier(recorder), now=NOW + timedelta(days=2), owner_chat=999
        )

        assert report.expired == 1
        assert recorder.chat_ids() == [999]

    def test_uses_user_currency_for_prices(self, session):
        recorder = Recorder()
        user = make_user(session, country="AE", currency="AED")
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        run_daily_maintenance(
            session, enabled_notifier(recorder), now=NOW + timedelta(days=2), owner_chat=999
        )

        assert "79 AED" in recorder.messages[0]["text"]

    def test_digest_counts_pending_payments_and_revenue(self, session):
        recorder = Recorder()
        user = make_user(session)
        paid = create_payment(session, user, provider="vodafone_cash", amount=299)
        approve_payment(session, paid, plan="pro_monthly", days=30, now=NOW)
        create_payment(session, user, provider="instapay", amount=75)

        report = run_daily_maintenance(
            session, enabled_notifier(recorder), now=NOW, owner_chat=999
        )
        digest = recorder.messages[-1]["text"]

        assert report.digest_sent is True
        assert "299" in digest
        assert "مدفوعات معلّقة" in digest

    def test_failed_send_is_counted_not_raised(self, session):
        def boom(url, body, timeout):
            raise RuntimeError("blocked")

        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=1, now=NOW)

        report = run_daily_maintenance(
            session,
            BotNotifier(token="T", transport=boom),
            now=NOW + timedelta(days=2),
            owner_chat=999,
        )

        assert report.expired == 1
        assert report.failed == 1          # expiry notice failed
        assert report.sent == 0
        assert report.digest_sent is False


class TestDailyGate:
    def test_runs_once_per_day(self, session, tmp_path):
        recorder = Recorder()
        state = tmp_path / "lifecycle.txt"
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=2, now=NOW)

        first = run_daily_if_due(
            session, now=NOW, state_path=state,
            notifier=enabled_notifier(recorder), owner_chat=999,
        )
        second = run_daily_if_due(
            session, now=NOW + timedelta(hours=6), state_path=state,
            notifier=enabled_notifier(recorder), owner_chat=999,
        )

        assert first is not None and first.reminded == 1
        assert second is None
        assert len(recorder.messages) == 2      # reminder + digest, not repeated

    def test_runs_again_next_day(self, session, tmp_path):
        recorder = Recorder()
        state = tmp_path / "lifecycle.txt"
        user = make_user(session)
        grant_subscription(session, user, "pro_monthly", days=2, now=NOW)

        run_daily_if_due(
            session, now=NOW, state_path=state,
            notifier=enabled_notifier(recorder), owner_chat=999,
        )
        again = run_daily_if_due(
            session, now=NOW + timedelta(days=1), state_path=state,
            notifier=enabled_notifier(recorder), owner_chat=999,
        )

        assert again is not None
        assert again.digest_sent is True

    def test_corrupt_state_file_does_not_block(self, session, tmp_path):
        state = tmp_path / "lifecycle.txt"
        state.write_text("not-a-date", encoding="utf-8")

        report = run_daily_if_due(
            session, now=NOW, state_path=state, notifier=BotNotifier(token=""),
        )
        assert report is not None
        assert state.read_text(encoding="utf-8") == "2026-11-14"


class TestDigestText:
    def test_reports_zeroes_cleanly(self, session):
        report = MaintenanceReport(
            expired=0, reminded=0, sent=0, failed=0, skipped=0, digest_sent=False
        )
        text = daily_digest_text(session, report, now=NOW)
        assert "2026-11-14" in text
        assert "0" in text
