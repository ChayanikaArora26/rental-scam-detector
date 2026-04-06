"""auth/schemas.py — Pydantic request/response models for auth endpoints."""
from pydantic import BaseModel, EmailStr, field_validator
from security.password import validate_strength


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        failures = validate_strength(v)
        if failures:
            raise ValueError("Password must have: " + ", ".join(failures))
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        failures = validate_strength(v)
        if failures:
            raise ValueError("Password must have: " + ", ".join(failures))
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds


class UserResponse(BaseModel):
    id: str
    email: str
    is_verified: bool
    role: str

    model_config = {"from_attributes": True}
