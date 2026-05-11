import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class FaceBiometric(Base):
    __tablename__ = "face_biometrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_object_key = Column(String(500), nullable=False)
    face_signature = Column(Text, nullable=False)
    provider = Column(String(100), nullable=False)
    provider_version = Column(String(50), nullable=False, server_default="1")
    quality_score = Column(Numeric(5, 4), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="face_biometrics")
