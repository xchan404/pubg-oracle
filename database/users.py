"""
User repository (Week 3 monetization layer)

Thin data-access helpers only: create/find users, keep their profile fresh,
attach partner referrals. Business rules (limits, plans) live in `services/`.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import User


def get_by_telegram_id(session: Session, telegram_id: int) -> User | None:
    return session.scalar(select(User).where(User.telegram_id == telegram_id))


def get_or_create(
    session: Session,
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    language: str = "ar",
    now: datetime | None = None,
) -> User:
    """
    Returns the user, creating it on first contact. Also refreshes the profile
    fields Telegram may have changed (username, first name).
    """
    now = now or datetime.utcnow()
    user = get_by_telegram_id(session, telegram_id)
    if user is not None:
        if username is not None and username != user.username:
            user.username = username
        if first_name is not None and first_name != user.first_name:
            user.first_name = first_name
        user.last_seen_at = now
        session.commit()
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        language=language or "ar",
        created_at=now,
        last_seen_at=now,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def touch(session: Session, user: User, now: datetime | None = None) -> None:
    user.last_seen_at = now or datetime.utcnow()
    session.commit()


def set_country_currency(session: Session, user: User, country: str, currency: str) -> User:
    user.country = country.upper()[:8]
    user.currency = currency.upper()[:8]
    session.commit()
    return user


def apply_referral(session: Session, user: User, code: str | None) -> bool:
    """
    Attaches a partner code once. Returns True when the code was applied.
    Existing attribution is never overwritten (first partner wins).
    """
    code = (code or "").strip()[:64]
    if not code or user.referred_by:
        return False
    user.referred_by = code
    session.commit()
    return True


def set_banned(session: Session, user: User, banned: bool = True) -> User:
    user.is_banned = banned
    session.commit()
    return user


def list_users(session: Session, *, limit: int = 100, offset: int = 0) -> list[User]:
    return list(session.scalars(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    ))
