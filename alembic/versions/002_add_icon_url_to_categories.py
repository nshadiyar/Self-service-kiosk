"""Add icon_url to categories

Revision ID: 002
Revises: 001
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('categories', sa.Column('icon_url', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('categories', 'icon_url')
