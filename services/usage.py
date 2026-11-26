"""
Usage metering (Week 3)

Free plan: 3 checks per rolling 24h. Pro/Business: unlimited.
When the free limit is hit, a paid credit is consumed if available.
Every allowed metered action is recorded so we can report usage to partners
and spot abuse.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import CreditLedger, UsageEvent, User
from services.entitlements import get_entitlement

FREE_WINDOW = timedelta(hours=24)
METERED_KINDS = frozenset({"check"})


@dataclass(frozen=True)
class UsageDecision:
    allowed: bool
    plan: str
    remaining: int | None   # None = unlimited
    used_credit: bool
    reason: str             # ok | unlimited | credit | limit_reached | banned | unmetered


def credit_balance(session: Session, user_id: int) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(CreditLedger.delta), 0))
        .where(CreditLedger.user_id == user_id)
    )
    return int(total or 0)


def add_credits(
    session: Session,
    user_id: int,
    amount: int,
    reason: str,
    now: datetime | None = None,
) -> int:
    """Appends to the ledger. Returns the new balance."""
    current = credit_balance(session, user_id)
    new_balance = current + int(amount)
    if new_balance < 0:
        raise ValueError("Credit balance cannot go negative")
    if amount:
        session.add(CreditLedger(
            user_id=user_id,
            delta=int(amount),
            reason=reason[:64],
            balance_after=new_balance,
            created_at=now or datetime.utcnow(),
        ))
        session.commit()
    return new_balance


def checks_used(session: Session, user_id: int, now: datetime | None = None) -> int:
    since = (now or datetime.utcnow()) - FREE_WINDOW
    used = session.scalar(
        select(func.count(UsageEvent.id))
        .where(
            UsageEvent.user_id == user_id,
            UsageEvent.kind == "check",
            UsageEvent.created_at >= since,
        )
    )
    return int(used or 0)


def _record(
    session: Session,
    user_id: int,
    kind: str,
    now: datetime,
    meta: str | None,
) -> None:
    session.add(UsageEvent(
        user_id=user_id,
        kind=kind[:32],
        created_at=now,
        meta=meta,
    ))
    session.commit()


def consume_check(
    session: Session,
    user: User,
    *,
    kind: str = "check",
    now: datetime | None = None,
    meta: str | None = None,
) -> UsageDecision:
    """
    Decides whether an action is allowed and records it.
    Call this before serving a paid/metered request.
    """
    now = now or datetime.utcnow()

    if user.is_banned:
        return UsageDecision(False, "banned", 0, False, "banned")

    entitlement = get_entitlement(session, user, now)

    # Only "check" is metered today; alerts/valuations are logged but free.
    if kind not in METERED_KINDS:
        _record(session, user.id, kind, now, meta)
        return UsageDecision(True, entitlement.plan, None, False, "unmetered")

    if entitlement.checks_per_day is None:
        _record(session, user.id, kind, now, meta)
        return UsageDecision(True, entitlement.plan, None, False, "unlimited")

    used = checks_used(session, user.id, now)
    if used < entitlement.checks_per_day:
        _record(session, user.id, kind, now, meta)
        remaining = entitlement.checks_per_day - used - 1
        return UsageDecision(True, entitlement.plan, remaining, False, "ok")

    # Free limit reached: fall back to purchased credits.
    if credit_balance(session, user.id) > 0:
        add_credits(session, user.id, -1, "check_credit", now)
        _record(session, user.id, kind, now, meta)
        return UsageDecision(True, entitlement.plan, 0, True, "credit")

    return UsageDecision(False, entitlement.plan, 0, False, "limit_reached")
