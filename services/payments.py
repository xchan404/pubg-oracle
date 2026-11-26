"""
Payments (Week 3)

Money-in records plus the approval step that turns a payment into an
entitlement (subscription) or credits. Manual wallets (Vodafone Cash /
InstaPay) are approved by an admin; Telegram Stars is reconciled here too.

Partner revenue share is calculated at approval time (25% of gross), so the
monthly partner report never needs to re-derive it.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Payment, User
from services.catalog import offer_grants
from services.entitlements import grant_subscription
from services.usage import add_credits

PARTNER_SHARE_RATE = 0.25
PROVIDERS = frozenset({"telegram_stars", "vodafone_cash", "instapay", "manual"})


@dataclass(frozen=True)
class PartnerPayout:
    partner_code: str
    gross: float
    share: float
    payments: int


def create_payment(
    session: Session,
    user: User,
    *,
    provider: str,
    amount: float,
    currency: str | None = None,
    external_ref: str | None = None,
    partner_code: str | None = None,
    proof_note: str | None = None,
    offer_code: str | None = None,
    now: datetime | None = None,
) -> Payment:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown payment provider: {provider}")
    if amount <= 0:
        raise ValueError("Payment amount must be positive")

    payment = Payment(
        user_id=user.id,
        provider=provider,
        amount=float(amount),
        currency=(currency or user.currency or "EGP").upper()[:8],
        status="pending",
        external_ref=external_ref,
        proof_note=proof_note,
        offer_code=offer_code,
        partner_code=(partner_code or user.referred_by),
        created_at=now or datetime.utcnow(),
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


def find_by_ref(session: Session, external_ref: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.external_ref == external_ref))


def approve_payment(
    session: Session,
    payment: Payment,
    *,
    plan: str | None = None,
    days: int | None = None,
    credits: int | None = None,
    reviewed_by: str = "admin",
    now: datetime | None = None,
) -> Payment:
    """
    Marks the payment approved and grants what was bought.
    Safe to call twice: an already-approved payment is returned untouched.
    """
    if payment.status == "approved":
        return payment
    if payment.status == "rejected":
        raise ValueError("Cannot approve a rejected payment")

    now = now or datetime.utcnow()

    # Auto-detect what was bought from the offer attached at checkout.
    if plan is None and credits is None and payment.offer_code:
        offer_plan, offer_days, offer_credits = offer_grants(payment.offer_code)
        plan = offer_plan
        if days is None:
            days = offer_days
        credits = offer_credits

    payment.status = "approved"
    payment.reviewed_at = now
    payment.reviewed_by = reviewed_by
    if payment.partner_code:
        payment.partner_share_amount = round(payment.amount * PARTNER_SHARE_RATE, 2)
    session.commit()

    user = session.get(User, payment.user_id)
    if user is None:
        raise ValueError(f"Payment {payment.id} points at a missing user")

    if plan:
        grant_subscription(
            session,
            user,
            plan,
            days=days,
            source=payment.provider,
            price_amount=payment.amount,
            currency=payment.currency,
            external_ref=payment.external_ref,
            now=now,
        )
    if credits:
        add_credits(session, user.id, int(credits), f"purchase:{payment.provider}", now)

    session.refresh(payment)
    return payment


def reject_payment(
    session: Session,
    payment: Payment,
    *,
    reviewed_by: str = "admin",
    reason: str | None = None,
    now: datetime | None = None,
) -> Payment:
    if payment.status == "approved":
        raise ValueError("Cannot reject an approved payment")

    payment.status = "rejected"
    payment.reviewed_at = now or datetime.utcnow()
    payment.reviewed_by = reviewed_by
    if reason:
        payment.proof_note = f"{payment.proof_note or ''}\nrejected: {reason}".strip()
    session.commit()
    session.refresh(payment)
    return payment


def partner_payouts(
    session: Session,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[PartnerPayout]:
    """Approved-payment totals per partner code (for the monthly report)."""
    query = select(Payment).where(
        Payment.status == "approved",
        Payment.partner_code.is_not(None),
    )
    if since is not None:
        query = query.where(Payment.reviewed_at >= since)
    if until is not None:
        query = query.where(Payment.reviewed_at <= until)

    totals: dict[str, list[float]] = {}
    for payment in session.scalars(query):
        code = payment.partner_code or ""
        bucket = totals.setdefault(code, [0.0, 0.0, 0.0])
        bucket[0] += payment.amount
        bucket[1] += payment.partner_share_amount or 0.0
        bucket[2] += 1

    return [
        PartnerPayout(code, round(gross, 2), round(share, 2), int(count))
        for code, (gross, share, count) in sorted(totals.items())
    ]
