from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer


class WalletResponse(BaseModel):
    id: UUID
    user_id: UUID
    balance: Decimal
    monthly_spent: Decimal
    monthly_limit: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("balance", "monthly_spent", "monthly_limit")
    def serialize_decimal(self, v: Decimal | None) -> float | None:
        return float(v) if v is not None else None


class TopUpRequest(BaseModel):
    user_id: UUID
    amount: Decimal
