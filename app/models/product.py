import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    stock_quantity = Column(Integer, default=0)
    image_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("Category", back_populates="products")
    facility = relationship("Facility", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
