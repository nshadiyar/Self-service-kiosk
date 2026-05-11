"""add photo_object_key to users

Revision ID: 004
Revises: 003
Create Date: 2026-05-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_object_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "photo_object_key")
