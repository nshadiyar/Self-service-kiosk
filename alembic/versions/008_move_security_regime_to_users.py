"""Move security regime to users

Revision ID: 008
Revises: 007
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "security_regime",
            sa.String(length=50),
            server_default=sa.text("'GENERAL'"),
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE users
        SET security_regime = COALESCE(f.security_regime, 'GENERAL')
        FROM facilities f
        WHERE users.facility_id = f.id
          AND users.role = 'INMATE';
        """
    )

    op.drop_column("facilities", "security_regime")


def downgrade() -> None:
    op.add_column(
        "facilities",
        sa.Column(
            "security_regime",
            sa.String(length=50),
            server_default=sa.text("'GENERAL'"),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE facilities f
        SET security_regime = COALESCE(u.security_regime, 'GENERAL')
        FROM users u
        WHERE u.facility_id = f.id
          AND u.role = 'INMATE'
          AND f.security_regime IS DISTINCT FROM COALESCE(u.security_regime, 'GENERAL');
        """
    )

    op.drop_column("users", "security_regime")
