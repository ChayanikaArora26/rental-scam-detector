"""
auth/router.py — All /auth/* endpoints.

POST /auth/register        → register + send verification email
GET  /auth/verify          → verify email token
POST /auth/login           → login → access token + refresh cookie
POST /auth/refresh         → rotate refresh token
POST /auth/logout          → revoke refresh token
POST /auth/forgot-password → send reset email
POST /auth/reset-password  → set new password
GET  /auth/me              → current user info
"""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import auth.service as svc
from auth.dependencies import get_current_user
from auth.schemas import (
    ForgotPasswordRequest, LoginRequest, RefreshRequest,
    RegisterRequest, ResetPasswordRequest, TokenResponse, UserResponse,
)
from database.models import User
from database.session import get_db
from email_service.service import send_verification_email, send_password_reset_email, send_login_alert
from security.rate_limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_OPTS = dict(httponly=True, secure=False, samesite="lax", max_age=7 * 24 * 3600)


# ── Register ───────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user, raw_token = await svc.register_user(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await send_verification_email(user.email, raw_token)
    return user


# ── Verify email ───────────────────────────────────────────────────────────

@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    try:
        await svc.verify_email_token(db, token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Email verified successfully"}


# ── Login ──────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/10minutes")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await svc.authenticate_user(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    access_token, expires_in = svc.create_access_token(user)
    raw_refresh = await svc.issue_refresh_token(
        db, user.id,
        device_fingerprint=request.headers.get("user-agent", "")[:255],
    )

    response.set_cookie(_REFRESH_COOKIE, raw_refresh, **_COOKIE_OPTS)

    # Fire login alert (don't await — non-blocking)
    import asyncio
    asyncio.create_task(send_login_alert(user.email, str(request.client.host)))

    return TokenResponse(access_token=access_token, expires_in=expires_in)


# ── Refresh ────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        user, new_refresh = await svc.rotate_refresh_token(db, refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    access_token, expires_in = svc.create_access_token(user)
    response.set_cookie(_REFRESH_COOKIE, new_refresh, **_COOKIE_OPTS)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


# ── Logout ─────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        await svc.revoke_refresh_token(db, refresh_token)
    response.delete_cookie(_REFRESH_COOKIE)
    return {"message": "Logged out"}


# ── Forgot password ────────────────────────────────────────────────────────

@router.post("/forgot-password")
@limiter.limit("3/10minutes")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await svc.create_password_reset_token(db, body.email)
    if result:
        user, raw_token = result
        await send_password_reset_email(user.email, raw_token)
    # Always return 200 to prevent email enumeration
    return {"message": "If that email is registered, a reset link has been sent"}


# ── Reset password ─────────────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        await svc.reset_password(db, body.token, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Password updated successfully"}


# ── Me ─────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
