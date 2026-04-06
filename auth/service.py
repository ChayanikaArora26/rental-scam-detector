"""
auth/service.py — Core auth business logic.

Handles:
  - User creation + email verification token
  - Login with failed-attempt tracking + lockout
  - JWT access token creation
  - Refresh token lifecycle (issue, rotate, revoke)
  - Password reset flow
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import EmailVerification, PasswordResetToken, RefreshToken, User
from security.password import hash_password, verify_password

settings = get_settings()


# ── Token helpers ──────────────────────────────────────────────────────────

def _sha256(token: str) -> str:
    """Store hashes, never raw tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user: User) -> tuple[str, int]:
    """Returns (signed JWT, expiry seconds)."""
    expire = _now() + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES)
    payload = {
        "sub":   user.id,
        "email": user.email,
        "role":  user.role,
        "iat":   _now().timestamp(),
        "exp":   expire.timestamp(),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, settings.JWT_ACCESS_EXPIRE_MINUTES * 60


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def create_refresh_token() -> str:
    """Cryptographically random opaque token (stored as hash in DB)."""
    return secrets.token_urlsafe(64)


# ── User queries ───────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ── Registration ───────────────────────────────────────────────────────────

async def register_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    """
    Create user + email verification token.
    Returns (user, raw_verification_token).
    Raises ValueError if email already exists.
    """
    existing = await get_user_by_email(db, email)
    if existing:
        raise ValueError("Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=email.lower(),
        password_hash=hash_password(password),
        is_verified=False,
    )
    db.add(user)
    await db.flush()   # get user.id without committing

    raw_token = secrets.token_urlsafe(32)
    ev = EmailVerification(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=_sha256(raw_token),
        expires_at=_now() + timedelta(hours=24),
    )
    db.add(ev)
    return user, raw_token


# ── Email verification ─────────────────────────────────────────────────────

async def verify_email_token(db: AsyncSession, raw_token: str) -> User:
    token_hash = _sha256(raw_token)
    result = await db.execute(
        select(EmailVerification).where(
            EmailVerification.token_hash == token_hash,
            EmailVerification.used == False,        # noqa: E712
            EmailVerification.expires_at > _now(),
        )
    )
    ev = result.scalar_one_or_none()
    if not ev:
        raise ValueError("Invalid or expired verification link")

    ev.used = True
    await db.execute(update(User).where(User.id == ev.user_id).values(is_verified=True))
    user = await get_user_by_id(db, ev.user_id)
    return user


# ── Login + lockout ────────────────────────────────────────────────────────

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)

    # Always run verify to prevent timing attacks even if user not found
    dummy_hash = "$2b$12$notarealhashfortimingattackprevention0000000"
    candidate_hash = user.password_hash if user else dummy_hash

    if not user:
        verify_password(password, candidate_hash)
        raise ValueError("Invalid credentials")

    # Check lockout
    if user.is_locked and user.locked_until and user.locked_until > _now():
        mins = int((user.locked_until - _now()).total_seconds() / 60) + 1
        raise ValueError(f"Account locked. Try again in {mins} minute(s)")

    # Reset stale lockout
    if user.is_locked and (not user.locked_until or user.locked_until <= _now()):
        user.is_locked = False
        user.failed_attempts = 0

    if not verify_password(password, candidate_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.MAX_FAILED_ATTEMPTS:
            user.is_locked = True
            user.locked_until = _now() + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        raise ValueError("Invalid credentials")

    # Successful login — reset counter
    user.failed_attempts = 0
    user.is_locked = False
    return user


# ── Refresh token lifecycle ────────────────────────────────────────────────

async def issue_refresh_token(
    db: AsyncSession,
    user_id: str,
    device_fingerprint: str | None = None,
) -> str:
    raw = create_refresh_token()
    rt = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=_sha256(raw),
        device_fingerprint=device_fingerprint,
        expires_at=_now() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )
    db.add(rt)
    return raw


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[User, str]:
    """
    Validate old refresh token, revoke it, issue a new one.
    Returns (user, new_raw_token).
    """
    token_hash = _sha256(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,          # noqa: E712
            RefreshToken.expires_at > _now(),
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise ValueError("Invalid or expired refresh token")

    # Revoke old token (rotation — prevents reuse)
    rt.revoked = True

    user = await get_user_by_id(db, rt.user_id)
    new_raw = await issue_refresh_token(db, rt.user_id, rt.device_fingerprint)
    return user, new_raw


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = _sha256(raw_token)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked=True)
    )


# ── Password reset ─────────────────────────────────────────────────────────

async def create_password_reset_token(db: AsyncSession, email: str) -> tuple[User, str] | None:
    """Returns (user, raw_token) or None if email not found (silent fail for security)."""
    user = await get_user_by_email(db, email)
    if not user:
        return None

    raw = secrets.token_urlsafe(32)
    prt = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=_sha256(raw),
        expires_at=_now() + timedelta(minutes=15),
    )
    db.add(prt)
    return user, raw


async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> User:
    token_hash = _sha256(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,       # noqa: E712
            PasswordResetToken.expires_at > _now(),
        )
    )
    prt = result.scalar_one_or_none()
    if not prt:
        raise ValueError("Invalid or expired reset link")

    prt.used = True
    await db.execute(
        update(User)
        .where(User.id == prt.user_id)
        .values(password_hash=hash_password(new_password), failed_attempts=0, is_locked=False)
    )
    return await get_user_by_id(db, prt.user_id)
