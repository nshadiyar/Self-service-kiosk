from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import OrderStatus


class DecimalSerializerModel(BaseModel):
    model_config = {"json_encoders": {Decimal: float}}


class DashboardSummaryResponse(DecimalSerializerModel):
    total_revenue: Decimal
    orders_count: int
    active_inmates: int
    pending_orders: int
    low_stock_products_count: int


class TimeSeriesPointResponse(DecimalSerializerModel):
    period: str
    total_amount: Decimal


class StatusCountResponse(BaseModel):
    status: OrderStatus
    count: int


class TopProductResponse(DecimalSerializerModel):
    product_id: UUID
    product_name: str
    total_quantity: int
    total_amount: Decimal


class TopFacilityResponse(DecimalSerializerModel):
    facility_id: UUID
    facility_name: str
    total_amount: Decimal
    orders_count: int


class RecentOrderResponse(DecimalSerializerModel):
    order_id: UUID
    inmate_id: UUID
    inmate_name: str
    facility_id: UUID
    facility_name: str
    total_amount: Decimal
    status: OrderStatus
    created_at: datetime


class LowStockProductResponse(DecimalSerializerModel):
    product_id: UUID
    product_name: str
    facility_id: UUID | None
    facility_name: str | None
    category_name: str | None
    vendor_name: str | None
    stock_quantity: int
    price: Decimal
    is_active: bool


class FacilityAnalyticsSummaryResponse(DecimalSerializerModel):
    total_spent: Decimal
    facilities_with_orders: int
    average_order_amount: Decimal
    top_facility_id: UUID | None
    top_facility_name: str | None


class FacilityAnalyticsRowResponse(DecimalSerializerModel):
    facility_id: UUID
    facility_name: str
    total_spent: Decimal
    orders_count: int
    average_order_amount: Decimal
    active_inmates: int
    top_product: str | None
    top_category: str | None


class FacilityDetailAnalyticsResponse(DecimalSerializerModel):
    facility_id: UUID
    facility_name: str
    total_spent: Decimal
    orders_count: int
    average_order_amount: Decimal
    active_inmates: int
    pending_orders: int
