"""Add security regime limits

Revision ID: 009
Revises: 008
Create Date: 2026-05-15
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_regime_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_regime", sa.String(length=50), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("security_regime"),
    )
    op.create_index(
        op.f("ix_security_regime_limits_security_regime"),
        "security_regime_limits",
        ["security_regime"],
        unique=True,
    )

    security_regime_limits = sa.table(
        "security_regime_limits",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("security_regime", sa.String(length=50)),
        sa.column("monthly_limit", sa.Numeric(12, 2)),
    )
    op.bulk_insert(
        security_regime_limits,
        [
            {"id": uuid.uuid4(), "security_regime": "GENERAL", "monthly_limit": 50000},
            {"id": uuid.uuid4(), "security_regime": "STRICT", "monthly_limit": 25000},
            {"id": uuid.uuid4(), "security_regime": "MAXIMUM", "monthly_limit": 10000},
        ],
    )

    op.execute(
        """
        UPDATE wallets w
        SET monthly_limit = srl.monthly_limit
        FROM users u
        JOIN security_regime_limits srl
          ON srl.security_regime = u.security_regime
        WHERE u.id = w.user_id
          AND u.role = 'INMATE'
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_security_regime_limits_security_regime"), table_name="security_regime_limits")
    op.drop_table("security_regime_limits")
