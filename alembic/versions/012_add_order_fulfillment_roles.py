"""add warehouse and courier roles with order fulfillment flow

Revision ID: 012_add_order_fulfillment_roles
Revises: 011_add_feedback
Create Date: 2026-05-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "012_add_order_fulfillment_roles"
down_revision: Union[str, None] = "011_add_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_enum_value_if_missing(enum_name: str, value: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = '{enum_name}'
                  AND e.enumlabel = '{value}'
            ) THEN
                ALTER TYPE {enum_name} ADD VALUE '{value}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _add_enum_value_if_missing("userrole", "WAREHOUSE_MANAGER")
    _add_enum_value_if_missing("userrole", "COURIER")

    _add_enum_value_if_missing("orderstatus", "PACKING")
    _add_enum_value_if_missing("orderstatus", "IN_TRANSIT")
    _add_enum_value_if_missing("orderstatus", "DELIVERED")
    _add_enum_value_if_missing("orderstatus", "FAILED_DELIVERY")

    op.add_column("orders", sa.Column("courier_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_orders_courier_id_users",
        "orders",
        "users",
        ["courier_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_orders_courier_id"), "orders", ["courier_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_courier_id"), table_name="orders")
    op.drop_constraint("fk_orders_courier_id_users", "orders", type_="foreignkey")
    op.drop_column("orders", "courier_id")
