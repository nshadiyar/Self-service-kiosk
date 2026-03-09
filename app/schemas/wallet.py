from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: Decimal
    monthly_spent: Decimal
    monthly_limit: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TopUpRequest(BaseModel):
    user_id: int
    amount: Decimal
