"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",             UUID(as_uuid=False), primary_key=True),
        sa.Column("email",          sa.String(255), nullable=False),
        sa.Column("password_hash",  sa.String(255), nullable=True),
        sa.Column("oauth_provider", sa.String(50),  nullable=True),
        sa.Column("oauth_id",       sa.String(255), nullable=True),
        sa.Column("is_verified",    sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("is_locked",      sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("failed_attempts",sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("locked_until",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("role",           sa.String(20),  nullable=False, server_default="user"),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email",    "users", ["email"],    unique=True)
    op.create_index("ix_users_oauth_id", "users", ["oauth_id"], unique=False)

    # ── refresh_tokens ───────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id",                 UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id",            UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash",         sa.String(255), nullable=False),
        sa.Column("device_fingerprint", sa.String(255), nullable=True),
        sa.Column("expires_at",         sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked",            sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at",         sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id",    "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # ── email_verifications ───────────────────────────────────────
    op.create_table(
        "email_verifications",
        sa.Column("id",         UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id",    UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used",       sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_verifications_user_id",    "email_verifications", ["user_id"])
    op.create_index("ix_email_verifications_token_hash", "email_verifications", ["token_hash"], unique=True)

    # ── password_reset_tokens ─────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id",         UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id",    UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used",       sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_tokens_user_id",    "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)

    # ── agent_logs ───────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id",               UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id",          UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("anonymised_input", sa.Text(), nullable=False),
        sa.Column("agent_response",   sa.Text(), nullable=True),
        sa.Column("tool_calls_json",  JSONB(),   nullable=True),
        sa.Column("tokens_used",      sa.Integer(), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_logs_user_id", "agent_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("agent_logs")
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verifications")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
