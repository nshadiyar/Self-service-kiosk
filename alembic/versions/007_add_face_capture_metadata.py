"""add face capture metadata

Revision ID: 007
Revises: 006
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("face_auth_attempts", sa.Column("effective_threshold", sa.Numeric(5, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("second_best_score", sa.Numeric(5, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("score_gap", sa.Numeric(5, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("quality_score", sa.Numeric(5, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("blur_variance", sa.Numeric(10, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("brightness", sa.Numeric(10, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("face_area_ratio", sa.Numeric(6, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("eye_count", sa.Integer(), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("capture_width", sa.Integer(), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("capture_height", sa.Integer(), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("client_face_count", sa.Integer(), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("client_blur_score", sa.Numeric(10, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("client_brightness", sa.Numeric(10, 4), nullable=True))
    op.add_column("face_auth_attempts", sa.Column("client_face_bbox", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("face_auth_attempts", "client_face_bbox")
    op.drop_column("face_auth_attempts", "client_brightness")
    op.drop_column("face_auth_attempts", "client_blur_score")
    op.drop_column("face_auth_attempts", "client_face_count")
    op.drop_column("face_auth_attempts", "capture_height")
    op.drop_column("face_auth_attempts", "capture_width")
    op.drop_column("face_auth_attempts", "eye_count")
    op.drop_column("face_auth_attempts", "face_area_ratio")
    op.drop_column("face_auth_attempts", "brightness")
    op.drop_column("face_auth_attempts", "blur_variance")
    op.drop_column("face_auth_attempts", "quality_score")
    op.drop_column("face_auth_attempts", "score_gap")
    op.drop_column("face_auth_attempts", "second_best_score")
    op.drop_column("face_auth_attempts", "effective_threshold")
