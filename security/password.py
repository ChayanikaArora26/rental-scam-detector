"""
security/password.py — Password hashing and strength validation.
Uses bcrypt with configurable cost factor (default 12).
"""
import hashlib
import re

from passlib.context import CryptContext
from config import get_settings

settings = get_settings()

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)

_STRENGTH_RULES = [
    (r".{8,}",               "at least 8 characters"),
    (r"[A-Z]",               "at least one uppercase letter"),
    (r"[0-9]",               "at least one number"),
    (r"[!@#$%^&*(),.?\":{}|<>_\-\+\=\[\]\\\/`~;']", "at least one special character"),
]


def _pre_hash(plain: str) -> str:
    """
    SHA-256 pre-hash so bcrypt's 72-byte limit is never hit.
    This is the pepper-free approach used by Django and others.
    """
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def hash_password(plain: str) -> str:
    return _ctx.hash(_pre_hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(_pre_hash(plain), hashed)


def validate_strength(password: str) -> list[str]:
    """Return list of unmet requirements. Empty = strong enough."""
    return [msg for pattern, msg in _STRENGTH_RULES if not re.search(pattern, password)]
