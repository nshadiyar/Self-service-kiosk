import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FaceAuthAttempt(Base):
    __tablename__ = "face_auth_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True)
    provider = Column(String(100), nullable=False)
    match_score = Column(Numeric(5, 4), nullable=True)
    threshold = Column(Numeric(5, 4), nullable=True)
    effective_threshold = Column(Numeric(5, 4), nullable=True)
    second_best_score = Column(Numeric(5, 4), nullable=True)
    score_gap = Column(Numeric(5, 4), nullable=True)
    quality_score = Column(Numeric(5, 4), nullable=True)
    liveness_score = Column(Numeric(5, 4), nullable=True)
    blur_variance = Column(Numeric(10, 4), nullable=True)
    brightness = Column(Numeric(10, 4), nullable=True)
    face_area_ratio = Column(Numeric(6, 4), nullable=True)
    eye_count = Column(Integer, nullable=True)
    capture_width = Column(Integer, nullable=True)
    capture_height = Column(Integer, nullable=True)
    client_face_count = Column(Integer, nullable=True)
    client_blur_score = Column(Numeric(10, 4), nullable=True)
    client_brightness = Column(Numeric(10, 4), nullable=True)
    client_face_bbox = Column(String(255), nullable=True)
    success = Column(Boolean, nullable=False, server_default="false")
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default="now()")

    user = relationship("User", back_populates="face_auth_attempts")
    facility = relationship("Facility")
