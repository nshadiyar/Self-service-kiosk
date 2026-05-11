"""add face quality and liveness

Revision ID: 006
Revises: 005
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("face_biometrics", sa.Column("quality_score", sa.Numeric(5, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("threshold", sa.Numeric(5, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("liveness_score", sa.Numeric(5, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("face_auth_attempts", "liveness_score")
    op.drop_column("face_auth_attempts", "threshold")
    op.drop_column("face_biometrics", "quality_score")
