from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.core.enums import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int


class RejectOrderRequest(BaseModel):
    reason: str


class OrderCreate(BaseModel):
    items: list[OrderItemCreate]


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    model_config = {"from_attributes": True}

    @field_serializer("unit_price", "subtotal")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_full_name: str | None = None
    facility_id: UUID
    facility_name: str | None = None
    status: OrderStatus
    total_amount: Decimal
    rejection_reason: str | None
    created_at: datetime
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}

    @field_serializer("total_amount")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)
