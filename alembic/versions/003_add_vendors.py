"""Add vendors table and vendor_id to products

Revision ID: 003
Revises: 002
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vendors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default='now()'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column('products', sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey('vendors.id'), nullable=True))


def downgrade():
    op.drop_column('products', 'vendor_id')
    op.drop_table('vendors')
