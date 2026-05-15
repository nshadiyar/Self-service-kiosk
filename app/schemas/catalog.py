from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


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
    category_name: str | None = None
    price: Decimal
    stock_quantity: int
    image_url: str | None
    vendor_id: UUID | None
    vendor_name: str | None = None
    facility_id: UUID | None = None
    facility_name: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("price")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    category_id: UUID
    facility_id: UUID | None = None
    vendor_id: UUID | None = None
    price: Decimal = Field(gt=0)
    stock_quantity: int = Field(ge=0, default=0)
    image_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    facility_id: UUID | None = None
    vendor_id: UUID | None = None
    price: Decimal | None = Field(default=None, gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    image_url: str | None = None
    is_active: bool | None = None


class ProductStockUpdate(BaseModel):
    stock_quantity: int = Field(ge=0)
    reason: str | None = None
