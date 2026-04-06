"""
database/models.py — All SQLAlchemy ORM models.

Tables:
  users                 — registered accounts
  refresh_tokens        — JWT refresh token store
  email_verifications   — email verification tokens
  password_reset_tokens — password reset tokens
  agent_logs            — anonymised LLM agent trace logs
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from database.session import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    password_hash    = Column(String(255), nullable=True)          # null for OAuth-only users
    oauth_provider   = Column(String(50),  nullable=True)          # "google" | None
    oauth_id         = Column(String(255), nullable=True, index=True)
    is_verified      = Column(Boolean, default=False, nullable=False)
    is_locked        = Column(Boolean, default=False, nullable=False)
    failed_attempts  = Column(Integer,  default=0,     nullable=False)
    locked_until     = Column(DateTime(timezone=True), nullable=True)
    role             = Column(String(20), default="user", nullable=False)  # "user" | "admin"
    created_at       = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # relationships
    refresh_tokens        = relationship("RefreshToken",       back_populates="user", cascade="all, delete-orphan")
    email_verifications   = relationship("EmailVerification",  back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    agent_logs            = relationship("AgentLog",           back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id                 = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id            = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash         = Column(String(255), nullable=False, index=True, unique=True)
    device_fingerprint = Column(String(255), nullable=True)
    expires_at         = Column(DateTime(timezone=True), nullable=False)
    revoked            = Column(Boolean, default=False, nullable=False)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="refresh_tokens")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id    = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used       = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="email_verifications")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id    = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used       = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="password_reset_tokens")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id          = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    anonymised_input = Column(Text, nullable=False)
    agent_response   = Column(Text, nullable=True)
    tool_calls_json  = Column(JSONB, nullable=True)      # full ReAct trace
    tokens_used      = Column(Integer, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="agent_logs")
