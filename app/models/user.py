import uuid
from datetime import date

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, String, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.core.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=True)
    iin = Column(String(12), unique=True, nullable=True, index=True)
    photo_url = Column(String(500), nullable=True)
    transfer_date = Column(Date, nullable=True)
    release_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    facility = relationship("Facility", back_populates="users")
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")
