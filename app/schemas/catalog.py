from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer


class VendorProductResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    stock_quantity: int
    is_active: bool

    model_config = {"from_attributes": True}

    @field_serializer("price")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)


class VendorResponse(BaseModel):
    id: UUID
    code: str
    name: str
    logo_url: str | None
    category_id: UUID | None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class VendorDetailResponse(VendorResponse):
    products: list[VendorProductResponse] = []


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    icon_url: str | None
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
    vendor_id: UUID | None
    is_active: bool

    model_config = {"from_attributes": True}

    @field_serializer("price")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)
