from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from app.core.enums import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int


class RejectOrderRequest(BaseModel):
    reason: str


class OrderCreate(BaseModel):
    items: list[OrderItemCreate]


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    user_id: int
    facility_id: int
    status: OrderStatus
    total_amount: Decimal
    rejection_reason: str | None
    created_at: datetime
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}
