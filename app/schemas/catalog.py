from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category_id: int
    price: Decimal
    stock_quantity: int
    image_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}
