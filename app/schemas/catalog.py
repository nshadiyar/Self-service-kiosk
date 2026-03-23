from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    category_id: UUID
    price: Decimal
    stock_quantity: int
    image_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}

    @field_serializer("price")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)
