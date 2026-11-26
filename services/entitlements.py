"""
Entitlements (Week 3)

Single source of truth for "what is this user allowed to do?".
The bot, the API and payment approval all read from here, so plan limits can
never drift between surfaces.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database.models import Subscription, User

PAID_PLANS = frozenset({"pro_monthly", "pro_annual", "business"})


@dataclass(frozen=True)
class PlanSpec:
    checks_per_day: int | None  # None = unlimited
    features: frozenset[str]


PLAN_SPECS: dict[str, PlanSpec] = {
    "free": PlanSpec(
        checks_per_day=3,
        features=frozenset({"delayed_deals"}),
    ),
    "pro_monthly": PlanSpec(
        checks_per_day=None,
        features=frozenset({"realtime_alerts", "unlimited_checks", "filters", "full_index"}),
    ),
    "pro_annual": PlanSpec(
        checks_per_day=None,
        features=frozenset({"realtime_alerts", "unlimited_checks", "filters", "full_index"}),
    ),
    "business": PlanSpec(
        checks_per_day=None,
        features=frozenset({
            "realtime_alerts", "unlimited_checks", "filters", "full_index",
            "bulk_export", "api_access", "badge", "seats_5",
        }),
    ),
}


@dataclass(frozen=True)
class Entitlement:
    plan: str
    is_paid: bool
    checks_per_day: int | None
    features: frozenset[str]
    expires_at: datetime | None
    subscription_id: int | None

    def has(self, feature: str) -> bool:
        return feature in self.features


def active_subscription(
    session: Session, user_id: int, now: datetime | None = None
) -> Subscription | None:
    """Newest non-expired active subscription, if any."""
    now = now or datetime.utcnow()
    return session.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )


def get_entitlement(
    session: Session, user: User, now: datetime | None = None
) -> Entitlement:
    """Falls back to the free plan when there is no active subscription."""
    sub = active_subscription(session, user.id, now)
    if sub is None:
        spec = PLAN_SPECS["free"]
        return Entitlement("free", False, spec.checks_per_day, spec.features, None, None)

    spec = PLAN_SPECS.get(sub.plan, PLAN_SPECS["free"])
    return Entitlement(
        plan=sub.plan,
        is_paid=True,
        checks_per_day=spec.checks_per_day,
        features=spec.features,
        expires_at=sub.expires_at,
        subscription_id=sub.id,
    )


def grant_subscription(
    session: Session,
    user: User,
    plan: str,
    *,
    days: int | None = None,
    expires_at: datetime | None = None,
    source: str = "manual",
    price_amount: float = 0.0,
    currency: str | None = None,
    external_ref: str | None = None,
    now: datetime | None = None,
) -> Subscription:
    """
    Grants (or renews) a paid plan.

    Renewals stack: if the user still has time left, the new period starts at
    the current expiry instead of resetting it.
    """
    if plan not in PAID_PLANS:
        raise ValueError(f"Unknown paid plan: {plan}")
    now = now or datetime.utcnow()

    if expires_at is None:
        if days is None or days <= 0:
            raise ValueError("Either days > 0 or expires_at is required")
        current = active_subscription(session, user.id, now)
        base = current.expires_at if current and current.expires_at > now else now
        expires_at = base + timedelta(days=days)

    sub = Subscription(
        user_id=user.id,
        plan=plan,
        status="active",
        started_at=now,
        expires_at=expires_at,
        source=source,
        price_amount=price_amount,
        currency=(currency or user.currency or "EGP").upper()[:8],
        external_ref=external_ref,
        created_at=now,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def expire_stale_subscriptions(session: Session, now: datetime | None = None) -> int:
    """Marks active subscriptions whose expiry has passed. Returns rows changed."""
    now = now or datetime.utcnow()
    result = session.execute(
        update(Subscription)
        .where(Subscription.status == "active", Subscription.expires_at <= now)
        .values(status="expired")
    )
    session.commit()
    return int(result.rowcount or 0)


def expiring_soon(
    session: Session, within_days: int = 3, now: datetime | None = None
) -> list[Subscription]:
    """Active subscriptions expiring within the window (renewal reminders)."""
    now = now or datetime.utcnow()
    limit = now + timedelta(days=within_days)
    return list(session.scalars(
        select(Subscription)
        .where(
            Subscription.status == "active",
            Subscription.expires_at > now,
            Subscription.expires_at <= limit,
        )
        .order_by(Subscription.expires_at.asc())
    ))
