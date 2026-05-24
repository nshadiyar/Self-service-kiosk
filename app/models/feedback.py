import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.enums import FeedbackDeliveryStatus, FeedbackType
from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String(50), nullable=False, index=True, default=FeedbackType.SUGGESTION.value)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    recipient_email = Column(String(255), nullable=False)
    delivery_status = Column(
        String(50),
        nullable=False,
        default=FeedbackDeliveryStatus.PENDING.value,
        index=True,
    )
    delivery_error = Column(String(1000), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default="now()")

    user = relationship("User")
    facility = relationship("Facility")
