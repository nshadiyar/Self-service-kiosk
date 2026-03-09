from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.core.enums import OrderStatus


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    facility_id = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    status = Column(Enum(OrderStatus), default="PENDING")
    total_amount = Column(Numeric(12, 2), default=0)
    rejection_reason = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate="now()")

    user = relationship("User", back_populates="orders")
    facility = relationship("Facility", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
