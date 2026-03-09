from sqlalchemy import Column, Integer, Numeric, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.core.enums import TransactionType


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    balance_after = Column(Numeric(12, 2))
    reference_type = Column(String(50))
    reference_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default="now()")

    wallet = relationship("Wallet", back_populates="transactions")
