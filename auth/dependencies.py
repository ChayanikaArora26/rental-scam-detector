"""
auth/dependencies.py — FastAPI dependencies for route protection.

Usage:
    @router.get("/me")
    async def me(user: User = Depends(get_current_user)):
        ...

    @router.get("/admin")
    async def admin(user: User = Depends(require_role("admin"))):
        ...
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.service import decode_access_token, get_user_by_id
from database.models import User
from database.session import get_db

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise exc
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise exc
    except JWTError:
        raise exc

    user = await get_user_by_id(db, user_id)
    if not user:
        raise exc
    return user


async def get_current_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")
    return user


def require_role(role: str):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check
