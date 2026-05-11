"""add face biometrics

Revision ID: 005
Revises: 004
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "face_biometrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_object_key", sa.String(length=500), nullable=False),
        sa.Column("face_signature", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_version", sa.String(length=50), server_default=sa.text("'1'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_face_biometrics_user_id"), "face_biometrics", ["user_id"], unique=False)

    op.create_table(
        "face_auth_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_face_auth_attempts_user_id"), "face_auth_attempts", ["user_id"], unique=False)
    op.create_index(op.f("ix_face_auth_attempts_facility_id"), "face_auth_attempts", ["facility_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_face_auth_attempts_facility_id"), table_name="face_auth_attempts")
    op.drop_index(op.f("ix_face_auth_attempts_user_id"), table_name="face_auth_attempts")
    op.drop_table("face_auth_attempts")
    op.drop_index(op.f("ix_face_biometrics_user_id"), table_name="face_biometrics")
    op.drop_table("face_biometrics")
