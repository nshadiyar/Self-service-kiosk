"""Add inmate fields to users (photo, transfer_date, release_date)

Revision ID: a1b2c3d4e5f6
Revises: e208b0d126fb
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e208b0d126fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("transfer_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("release_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "release_date")
    op.drop_column("users", "transfer_date")
    op.drop_column("users", "photo_url")
