"""
Dashboards API (user + admin)
=============================

Two surfaces, one source of truth:

* `/api/me*`  — the subscriber's own data, authenticated with Telegram
  WebApp `initData` (HMAC-SHA256, verified against BOT_TOKEN).
* `/api/admin*` — owner operations, authenticated with a local admin token
  (`ADMIN_DASHBOARD_TOKEN`, or an auto-generated `logs/admin_token.txt`) or,
  when opened inside Telegram, the owner's `MY_CHAT_ID`.

Nothing here invents numbers: every value is read from the monetization tables
or the freshness probe. Unknown values are returned as null and the UI renders
"—".
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from config import LOGS_DIR
from database import users as users_repo
from database.db import get_db, init_db
from database.models import CreditLedger, Payment, Subscription, User
from services.catalog import CURRENCY_BY_COUNTRY, OFFERS, resolve_price
from services.entitlements import (
    expiring_soon,
    get_entitlement,
    grant_subscription,
)
from services.payments import approve_payment, partner_payouts, reject_payment
from services.usage import add_credits, checks_used, credit_balance

# Tables must exist before the first dashboard request. This is best-effort so
# that importing the API never crashes (read-only checkouts, import-time tests);
# a real failure still surfaces on the first query.
try:
    init_db()
except Exception as _init_err:  # pragma: no cover - environment dependent
    logging.getLogger("pubg_scraper").warning(
        "Dashboards could not initialise the database: %s", _init_err
    )

router = APIRouter(prefix="/api", tags=["dashboards"])

PLAN_LABELS = {
    "free": "مجاني",
    "pro_monthly": "Pro شهري",
    "pro_annual": "Pro سنوي",
    "business": "Business",
}

ADMIN_TOKEN_ENV = "ADMIN_DASHBOARD_TOKEN"
ADMIN_TOKEN_FILE = LOGS_DIR / "admin_token.txt"
INIT_DATA_MAX_AGE = 24 * 60 * 60  # seconds


# ─── Authentication helpers ──────────────────────────────────────────────────

def verify_telegram_init_data(init_data: str, bot_token: str,
                              max_age_seconds: int = INIT_DATA_MAX_AGE) -> dict | None:
    """
    Validates Telegram WebApp initData per the official algorithm:
    secret = HMAC_SHA256("WebAppData", bot_token)
    hash   = HMAC_SHA256(secret, data_check_string)
    Returns the parsed `user` object, or None when invalid/expired.
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError:
        return None
    if auth_date and (time.time() - auth_date) > max_age_seconds:
        return None

    try:
        return json.loads(data.get("user") or "{}")
    except json.JSONDecodeError:
        return None


def _dev_login_enabled() -> bool:
    return os.getenv("DASHBOARD_DEV_LOGIN", "").strip().lower() in {"1", "true", "yes"}


def current_user(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
    db: Session = Depends(get_db),
) -> User:
    """Resolves the caller to a User row (created on first contact)."""
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    telegram_user: dict | None = None

    if x_telegram_init_data:
        telegram_user = verify_telegram_init_data(x_telegram_init_data, bot_token)
    elif _dev_login_enabled() and x_dev_telegram_id:
        # Local-only escape hatch for screenshots/tests. Never enabled by default.
        try:
            telegram_user = {"id": int(x_dev_telegram_id), "username": "dev",
                             "first_name": "Dev"}
        except ValueError:
            telegram_user = None

    if not telegram_user or "id" not in telegram_user:
        raise HTTPException(
            status_code=401,
            detail="افتح هذه اللوحة من داخل بوت تليجرام.",
        )

    return users_repo.get_or_create(
        db,
        int(telegram_user["id"]),
        username=telegram_user.get("username"),
        first_name=telegram_user.get("first_name"),
        language=(telegram_user.get("language_code") or "ar")[:2],
    )


def admin_token() -> str:
    """
    Admin secret: env var wins; otherwise a random token persisted locally.
    The token is never returned by an unauthenticated endpoint.
    """
    env_token = os.getenv(ADMIN_TOKEN_ENV, "").strip()
    if env_token:
        return env_token
    if ADMIN_TOKEN_FILE.exists():
        saved = ADMIN_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    generated = secrets.token_urlsafe(32)
    ADMIN_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_TOKEN_FILE.write_text(generated, encoding="utf-8")
    return generated


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> str:
    if x_admin_token and hmac.compare_digest(x_admin_token, admin_token()):
        return "token"

    owner_id = os.getenv("MY_CHAT_ID", "").strip()
    if owner_id and x_telegram_init_data:
        telegram_user = verify_telegram_init_data(
            x_telegram_init_data, os.getenv("BOT_TOKEN", "").strip()
        )
        if telegram_user and str(telegram_user.get("id")) == owner_id:
            return "telegram_owner"

    raise HTTPException(status_code=401, detail="مطلوب توكن إدارة صالح.")


# ─── Serialization helpers ───────────────────────────────────────────────────

def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _payment_dict(payment: Payment, user: User | None = None) -> dict:
    payload = {
        "id": payment.id,
        "provider": payment.provider,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "offer_code": payment.offer_code,
        "external_ref": payment.external_ref,
        "proof_note": payment.proof_note,
        "partner_code": payment.partner_code,
        "partner_share_amount": payment.partner_share_amount,
        "created_at": _iso(payment.created_at),
        "reviewed_at": _iso(payment.reviewed_at),
        "reviewed_by": payment.reviewed_by,
    }
    if user is not None:
        payload["user"] = {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
        }
    return payload


def _plan_payload(entitlement, now: datetime) -> dict:
    days_left = None
    if entitlement.expires_at:
        days_left = max(0, (entitlement.expires_at - now).days)
    return {
        "code": entitlement.plan,
        "label": PLAN_LABELS.get(entitlement.plan, entitlement.plan),
        "is_paid": entitlement.is_paid,
        "expires_at": _iso(entitlement.expires_at),
        "days_left": days_left,
        "checks_per_day": entitlement.checks_per_day,
        "features": sorted(entitlement.features),
    }


def _user_dict(user: User, db: Session, now: datetime) -> dict:
    entitlement = get_entitlement(db, user, now)
    used = checks_used(db, user.id, now)
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "country": user.country,
        "currency": user.currency,
        "referred_by": user.referred_by,
        "is_banned": user.is_banned,
        "created_at": _iso(user.created_at),
        "last_seen_at": _iso(user.last_seen_at),
        "plan": _plan_payload(entitlement, now),
        "checks_used_24h": used,
        "credits": credit_balance(db, user.id),
    }


def _offer_list(currency: str) -> list[dict]:
    return [
        {
            "code": offer.code,
            "title_ar": offer.title_ar,
            "days": offer.days,
            "credits": offer.credits,
            "price": resolve_price(offer, currency),
            "currency": currency if currency in offer.prices else "EGP",
        }
        for offer in OFFERS.values()
    ]


# ─── User dashboard ──────────────────────────────────────────────────────────

@router.get("/config")
def public_config():
    """Public, non-secret bits the dashboards need before authentication."""
    return {
        "bot_username": os.getenv("BOT_USERNAME", "").strip(),
        "countries": [
            {"code": code, "currency": currency}
            for code, currency in CURRENCY_BY_COUNTRY.items()
        ],
    }


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    entitlement = get_entitlement(db, user, now)
    used = checks_used(db, user.id, now)
    limit = entitlement.checks_per_day
    payments = list(db.scalars(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(20)
    ))

    return {
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "country": user.country,
            "currency": user.currency,
            "referred_by": user.referred_by,
            "created_at": _iso(user.created_at),
        },
        "plan": _plan_payload(entitlement, now),
        "usage": {
            "used_24h": used,
            "limit": limit,
            "remaining": None if limit is None else max(0, limit - used),
        },
        "credits": credit_balance(db, user.id),
        "payments": [_payment_dict(p) for p in payments],
        "offers": _offer_list(user.currency or "EGP"),
        "bot_username": os.getenv("BOT_USERNAME", "").strip(),
    }


class LocaleRequest(BaseModel):
    country: str


@router.post("/me/locale")
def set_locale(
    payload: LocaleRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    country = (payload.country or "").strip().upper()[:8]
    currency = CURRENCY_BY_COUNTRY.get(country)
    if currency is None:
        raise HTTPException(status_code=400, detail="دولة غير مدعومة حاليًا.")
    users_repo.set_country_currency(db, user, country, currency)
    return {"country": country, "currency": currency}


# ─── Admin dashboard ─────────────────────────────────────────────────────────

@router.get("/admin/session")
def admin_session(role: str = Depends(require_admin)):
    return {
        "ok": True,
        "role": role,
        "token_source": "env" if os.getenv(ADMIN_TOKEN_ENV, "").strip() else "file",
        "token_path": str(ADMIN_TOKEN_FILE),
    }


@router.get("/admin/overview")
def admin_overview(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    users_total = int(db.scalar(select(func.count(User.id))) or 0)
    users_new_7d = int(db.scalar(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    ) or 0)
    paid_active = int(db.scalar(
        select(func.count(func.distinct(Subscription.user_id))).where(
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
    ) or 0)
    pending_count = int(db.scalar(
        select(func.count(Payment.id)).where(Payment.status == "pending")
    ) or 0)

    revenue_rows = db.execute(
        select(
            Payment.currency,
            func.coalesce(func.sum(Payment.amount), 0.0),
            func.count(Payment.id),
        )
        .where(Payment.status == "approved", Payment.reviewed_at >= month_start)
        .group_by(Payment.currency)
    ).all()

    lifetime_rows = db.execute(
        select(
            Payment.currency,
            func.coalesce(func.sum(Payment.amount), 0.0),
            func.count(Payment.id),
        )
        .where(Payment.status == "approved")
        .group_by(Payment.currency)
    ).all()

    balances = db.execute(
        select(CreditLedger.user_id, func.coalesce(func.sum(CreditLedger.delta), 0))
        .group_by(CreditLedger.user_id)
    ).all()
    credits_outstanding = int(sum(int(b or 0) for _, b in balances if (b or 0) > 0))

    from intelligence.freshness import get_freshness
    freshness = get_freshness()

    recent_payments = db.execute(
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
        .order_by(Payment.created_at.desc())
        .limit(6)
    ).all()

    return {
        "users": {"total": users_total, "new_7d": users_new_7d, "paid_active": paid_active},
        "payments": {"pending": pending_count},
        "revenue_month": [
            {"currency": cur, "amount": round(float(amount), 2), "count": int(count)}
            for cur, amount, count in revenue_rows
        ],
        "revenue_lifetime": [
            {"currency": cur, "amount": round(float(amount), 2), "count": int(count)}
            for cur, amount, count in lifetime_rows
        ],
        "credits_outstanding": credits_outstanding,
        "expiring_3d": len(expiring_soon(db, 3, now)),
        "partners": [
            {"code": p.partner_code, "gross": p.gross, "share": p.share, "payments": p.payments}
            for p in partner_payouts(db)
        ],
        "freshness": freshness,
        "recent_payments": [_payment_dict(p, u) for p, u in recent_payments],
    }


@router.get("/admin/users")
def admin_users(
    query: str = "",
    limit: int = 50,
    offset: int = 0,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    limit = max(1, min(200, int(limit)))
    stmt = select(User)
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(or_(
            User.username.ilike(like),
            User.first_name.ilike(like),
            cast(User.telegram_id, String).like(like),
        ))
    stmt = stmt.order_by(User.created_at.desc()).offset(max(0, offset)).limit(limit)

    now = datetime.utcnow()
    rows = [_user_dict(u, db, now) for u in db.scalars(stmt)]
    total = int(db.scalar(select(func.count(User.id))) or 0)
    return {"items": rows, "total": total}


@router.get("/admin/payments")
def admin_payments(
    status: str = "pending",
    limit: int = 100,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    limit = max(1, min(300, int(limit)))
    stmt = (
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    if status and status != "all":
        stmt = stmt.where(Payment.status == status)

    items = [_payment_dict(p, u) for p, u in db.execute(stmt).all()]
    counts = {
        row[0]: int(row[1])
        for row in db.execute(
            select(Payment.status, func.count(Payment.id)).group_by(Payment.status)
        ).all()
    }
    return {"items": items, "counts": counts}


class ApproveRequest(BaseModel):
    plan: str | None = None
    days: int | None = None
    credits: int | None = None


@router.post("/admin/payments/{payment_id}/approve")
def admin_approve_payment(
    payment_id: int,
    payload: ApproveRequest | None = None,
    role: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="الدفعة غير موجودة.")
    body = payload or ApproveRequest()
    try:
        updated = approve_payment(
            db, payment,
            plan=body.plan, days=body.days, credits=body.credits,
            reviewed_by=f"admin:{role}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payment_dict(updated, db.get(User, updated.user_id))


class RejectRequest(BaseModel):
    reason: str | None = None


@router.post("/admin/payments/{payment_id}/reject")
def admin_reject_payment(
    payment_id: int,
    payload: RejectRequest | None = None,
    role: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="الدفعة غير موجودة.")
    body = payload or RejectRequest()
    try:
        updated = reject_payment(db, payment, reviewed_by=f"admin:{role}",
                                 reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _payment_dict(updated, db.get(User, updated.user_id))


class GrantRequest(BaseModel):
    plan: str
    days: int | None = None


@router.post("/admin/users/{user_id}/grant")
def admin_grant(
    user_id: int,
    payload: GrantRequest,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")
    days = payload.days or (365 if payload.plan == "pro_annual" else 30)
    try:
        grant_subscription(db, user, payload.plan, days=days, source="admin")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _user_dict(user, db, datetime.utcnow())


class CreditsRequest(BaseModel):
    amount: int
    reason: str = "admin_adjustment"


@router.post("/admin/users/{user_id}/credits")
def admin_credits(
    user_id: int,
    payload: CreditsRequest,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")
    try:
        balance = add_credits(db, user.id, int(payload.amount),
                              payload.reason or "admin_adjustment")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user_id": user.id, "credits": balance}


class BanRequest(BaseModel):
    banned: bool = True


@router.post("/admin/users/{user_id}/ban")
def admin_ban(
    user_id: int,
    payload: BanRequest,
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود.")
    users_repo.set_banned(db, user, payload.banned)
    return {"user_id": user.id, "is_banned": user.is_banned}


@router.get("/admin/partners")
def admin_partners(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "items": [
            {"code": p.partner_code, "gross": p.gross, "share": p.share,
             "payments": p.payments}
            for p in partner_payouts(db)
        ]
    }


@router.get("/admin/data")
def admin_data(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    from intelligence.freshness import get_freshness

    now = datetime.utcnow()
    active_subs = int(db.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active", Subscription.expires_at > now
        )
    ) or 0)
    return {
        "freshness": get_freshness(),
        "counts": {
            "users": int(db.scalar(select(func.count(User.id))) or 0),
            "payments": int(db.scalar(select(func.count(Payment.id))) or 0),
            "active_subscriptions": active_subs,
        },
        "admin_token_path": str(ADMIN_TOKEN_FILE),
    }


@router.post("/admin/retrain")
async def admin_retrain(_: str = Depends(require_admin)):
    """Owner-triggered retrain. Same work as /mlops/retrain, but authenticated."""
    from ml.retrain_service import run_retrain_service

    try:
        await asyncio.to_thread(run_retrain_service, force=True)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        raise HTTPException(status_code=500, detail=f"تعذر إعادة التدريب: {exc}") from exc
    return {"status": "success", "message": "تمت إعادة تدريب النموذج بنجاح."}

