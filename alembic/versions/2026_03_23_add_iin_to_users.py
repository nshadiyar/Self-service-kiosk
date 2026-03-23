"""Add IIN to users

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("iin", sa.String(12), nullable=True))
    op.create_index(op.f("ix_users_iin"), "users", ["iin"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_iin"), table_name="users")
    op.drop_column("users", "iin")
