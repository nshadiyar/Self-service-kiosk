import uuid

from sqlalchemy import Column, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SecurityRegimeLimit(Base):
    __tablename__ = "security_regime_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    security_regime = Column(String(50), unique=True, nullable=False, index=True)
    monthly_limit = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
