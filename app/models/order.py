import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.core.enums import OrderStatus


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=False)
    status = Column(Enum(OrderStatus), default="PENDING")
    total_amount = Column(Numeric(12, 2), default=0)
    rejection_reason = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="orders")
    facility = relationship("Facility", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
