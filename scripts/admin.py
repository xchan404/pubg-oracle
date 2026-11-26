"""
Admin CLI for the monetization layer (Week 3).

Operate users, plans, credits and manual wallet payments without the bot UI.

Examples:
    python scripts/admin.py user 123456789
    python scripts/admin.py grant 123456789 pro_monthly --days 30
    python scripts/admin.py credits 123456789 5 --reason manual
    python scripts/admin.py payments --status pending
    python scripts/admin.py approve 12 --plan pro_monthly --days 30
    python scripts/admin.py reject 13 --reason "no proof"
    python scripts/admin.py partners --since 2026-11-01
    python scripts/admin.py expire
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from database.db import SessionLocal, init_db  # noqa: E402
from database.models import Payment, User  # noqa: E402
from database.users import get_by_telegram_id  # noqa: E402
from services.entitlements import (  # noqa: E402
    expire_stale_subscriptions,
    get_entitlement,
    grant_subscription,
)
from services.payments import (  # noqa: E402
    approve_payment,
    partner_payouts,
    reject_payment,
)
from services.usage import add_credits, checks_used, credit_balance  # noqa: E402


def _user_or_exit(session, telegram_id: int) -> User:
    user = get_by_telegram_id(session, telegram_id)
    if user is None:
        raise SystemExit(f"No user with telegram_id={telegram_id}")
    return user


def cmd_user(args) -> None:
    with SessionLocal() as session:
        user = _user_or_exit(session, args.telegram_id)
        ent = get_entitlement(session, user)
        print(f"telegram_id : {user.telegram_id}")
        print(f"name        : {user.first_name or '-'} (@{user.username or '-'})")
        print(f"country     : {user.country or '-'} | currency: {user.currency}")
        print(f"referred_by : {user.referred_by or '-'}")
        print(f"banned      : {user.is_banned}")
        print(f"plan        : {ent.plan} (paid={ent.is_paid})")
        print(f"expires_at  : {ent.expires_at.isoformat() if ent.expires_at else '-'}")
        print(f"checks_24h  : {checks_used(session, user.id)}"
              f" / {ent.checks_per_day if ent.checks_per_day is not None else 'unlimited'}")
        print(f"credits     : {credit_balance(session, user.id)}")


def cmd_grant(args) -> None:
    with SessionLocal() as session:
        user = _user_or_exit(session, args.telegram_id)
        sub = grant_subscription(
            session, user, args.plan,
            days=args.days, source=args.source,
            price_amount=args.price, currency=args.currency,
        )
        print(f"granted {sub.plan} to {user.telegram_id} "
              f"until {sub.expires_at.isoformat()} (source={sub.source})")


def cmd_credits(args) -> None:
    with SessionLocal() as session:
        user = _user_or_exit(session, args.telegram_id)
        balance = add_credits(session, user.id, args.amount, args.reason)
        print(f"credits for {user.telegram_id}: {balance}")


def cmd_payments(args) -> None:
    with SessionLocal() as session:
        query = select(Payment).order_by(Payment.created_at.desc()).limit(args.limit)
        if args.status:
            query = query.where(Payment.status == args.status)
        payments = list(session.scalars(query))
        if not payments:
            print("no payments")
            return
        for p in payments:
            print(f"#{p.id:<5} user={p.user_id:<6} {p.status:<8} "
                  f"{p.amount:>8,.2f} {p.currency} {p.provider:<15} "
                  f"offer={p.offer_code or '-':<12} "
                  f"ref={p.external_ref or '-'} partner={p.partner_code or '-'}")


def cmd_approve(args) -> None:
    with SessionLocal() as session:
        payment = session.get(Payment, args.payment_id)
        if payment is None:
            raise SystemExit(f"No payment with id={args.payment_id}")
        approve_payment(
            session, payment,
            plan=args.plan, days=args.days, credits=args.credits,
            reviewed_by=args.by,
        )
        print(f"payment #{payment.id} approved: {payment.amount:,.2f} {payment.currency}"
              f" | partner share={payment.partner_share_amount or 0:,.2f}")
        user = session.get(User, payment.user_id)
        if user is not None:
            ent = get_entitlement(session, user)
            print(f"user {user.telegram_id}: plan={ent.plan} "
                  f"expires={ent.expires_at.isoformat() if ent.expires_at else '-'} "
                  f"credits={credit_balance(session, user.id)}")
        if not args.plan and not args.credits and not payment.offer_code:
            print("WARNING: nothing granted — pass --plan/--credits or set offer_code")


def cmd_reject(args) -> None:
    with SessionLocal() as session:
        payment = session.get(Payment, args.payment_id)
        if payment is None:
            raise SystemExit(f"No payment with id={args.payment_id}")
        reject_payment(session, payment, reviewed_by=args.by, reason=args.reason)
        print(f"payment #{payment.id} rejected")


def cmd_partners(args) -> None:
    since = datetime.fromisoformat(args.since) if args.since else None
    with SessionLocal() as session:
        payouts = partner_payouts(session, since=since)
        if not payouts:
            print("no partner revenue yet")
            return
        print(f"{'partner':<24} {'payments':>8} {'gross':>12} {'share 25%':>12}")
        for p in payouts:
            print(f"{p.partner_code:<24} {p.payments:>8} {p.gross:>12,.2f} {p.share:>12,.2f}")


def cmd_expire(args) -> None:
    with SessionLocal() as session:
        count = expire_stale_subscriptions(session)
        print(f"expired subscriptions: {count}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monetization admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("user", help="show a user's plan and usage")
    p.add_argument("telegram_id", type=int)
    p.set_defaults(func=cmd_user)

    p = sub.add_parser("grant", help="grant or renew a paid plan")
    p.add_argument("telegram_id", type=int)
    p.add_argument("plan", choices=["pro_monthly", "pro_annual", "business"])
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--source", default="manual")
    p.add_argument("--price", type=float, default=0.0)
    p.add_argument("--currency", default=None)
    p.set_defaults(func=cmd_grant)

    p = sub.add_parser("credits", help="add or remove credits")
    p.add_argument("telegram_id", type=int)
    p.add_argument("amount", type=int)
    p.add_argument("--reason", default="manual")
    p.set_defaults(func=cmd_credits)

    p = sub.add_parser("payments", help="list payments")
    p.add_argument("--status", choices=["pending", "approved", "rejected", "refunded"])
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_payments)

    p = sub.add_parser("approve", help="approve a payment and grant access")
    p.add_argument("payment_id", type=int)
    p.add_argument("--plan", choices=["pro_monthly", "pro_annual", "business"])
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--credits", type=int)
    p.add_argument("--by", default="admin")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="reject a payment")
    p.add_argument("payment_id", type=int)
    p.add_argument("--reason", default=None)
    p.add_argument("--by", default="admin")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("partners", help="monthly partner revenue report")
    p.add_argument("--since", default=None, help="ISO date, e.g. 2026-11-01")
    p.set_defaults(func=cmd_partners)

    p = sub.add_parser("expire", help="mark elapsed subscriptions expired")
    p.set_defaults(func=cmd_expire)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    init_db()
    args.func(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
