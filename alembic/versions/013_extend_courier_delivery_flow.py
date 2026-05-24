"""extend courier delivery flow

Revision ID: 013_extend_courier_delivery_flow
Revises: 012_add_order_fulfillment_roles
Create Date: 2026-05-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_extend_courier_delivery_flow"
down_revision: Union[str, None] = "012_add_order_fulfillment_roles"
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
    _add_enum_value_if_missing("orderstatus", "READY_FOR_SHIPMENT")
    _add_enum_value_if_missing("orderstatus", "OUT_FOR_DELIVERY")
    _add_enum_value_if_missing("orderstatus", "ARRIVED_AT_FACILITY")
    op.add_column("orders", sa.Column("recipient_employee_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "recipient_employee_name")
