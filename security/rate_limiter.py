"""
security/rate_limiter.py — IP-based rate limiting via slowapi.
Also provides account lockout helpers (stored in DB via auth service).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# One shared limiter instance — imported by routers that need it
limiter = Limiter(key_func=get_remote_address)
