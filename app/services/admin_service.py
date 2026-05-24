from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import OrderStatus, UserRole
from app.core.exceptions import NotFoundError
from app.models.category import Category
from app.models.facility import Facility
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.admin import (
    DashboardSummaryResponse,
    FacilityAnalyticsRowResponse,
    FacilityAnalyticsSummaryResponse,
    FacilityDetailAnalyticsResponse,
    LowStockProductResponse,
    RecentOrderResponse,
    StatusCountResponse,
    TimeSeriesPointResponse,
    TopFacilityResponse,
    TopProductResponse,
)


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _active_order_filter():
        return Order.status == OrderStatus.DELIVERED

    @staticmethod
    def _date_filters(date_from: date | None = None, date_to: date | None = None):
        filters = []
        order_date = func.date(Order.created_at)
        if date_from is not None:
            filters.append(order_date >= date_from)
        if date_to is not None:
            filters.append(order_date <= date_to)
        return filters

    async def dashboard_summary(self, *, date_from: date | None = None, date_to: date | None = None) -> DashboardSummaryResponse:
        filters = [self._active_order_filter(), *self._date_filters(date_from, date_to)]
        total_revenue = await self.db.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(*filters)
        )
        orders_count = await self.db.scalar(select(func.count(Order.id)).where(*self._date_filters(date_from, date_to)))
        active_inmates = await self.db.scalar(
            select(func.count(User.id)).where(User.role == UserRole.INMATE, User.is_active == True)
        )
        pending_orders = await self.db.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING, *self._date_filters(date_from, date_to))
        )
        low_stock_count = await self.db.scalar(
            select(func.count(Product.id)).where(Product.is_active == True, Product.stock_quantity <= 10)
        )
        return DashboardSummaryResponse(
            total_revenue=total_revenue or Decimal(0),
            orders_count=orders_count or 0,
            active_inmates=active_inmates or 0,
            pending_orders=pending_orders or 0,
            low_stock_products_count=low_stock_count or 0,
        )

    async def spending_trend(self, *, group_by: str = "day", date_from: date | None = None, date_to: date | None = None) -> list[TimeSeriesPointResponse]:
        date_expr = func.date_trunc(group_by, Order.created_at)
        result = await self.db.execute(
            select(
                func.to_char(date_expr, "YYYY-MM-DD").label("period"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_amount"),
            )
            .where(self._active_order_filter(), *self._date_filters(date_from, date_to))
            .group_by(date_expr)
            .order_by(date_expr.asc())
        )
        return [TimeSeriesPointResponse(period=row.period, total_amount=row.total_amount) for row in result]

    async def orders_by_status(self, *, date_from: date | None = None, date_to: date | None = None) -> list[StatusCountResponse]:
        result = await self.db.execute(
            select(Order.status, func.count(Order.id).label("count"))
            .where(*self._date_filters(date_from, date_to))
            .group_by(Order.status)
            .order_by(Order.status)
        )
        return [StatusCountResponse(status=row.status, count=row.count) for row in result]

    async def top_products(self, *, limit: int = 5, date_from: date | None = None, date_to: date | None = None) -> list[TopProductResponse]:
        result = await self.db.execute(
            select(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_amount"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(self._active_order_filter(), *self._date_filters(date_from, date_to))
            .group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.subtotal).desc())
            .limit(limit)
        )
        return [TopProductResponse(**row._mapping) for row in result]

    async def top_facilities(self, *, limit: int = 5, date_from: date | None = None, date_to: date | None = None) -> list[TopFacilityResponse]:
        result = await self.db.execute(
            select(
                Facility.id.label("facility_id"),
                Facility.name.label("facility_name"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_amount"),
                func.count(Order.id).label("orders_count"),
            )
            .join(Order, Order.facility_id == Facility.id)
            .where(self._active_order_filter(), *self._date_filters(date_from, date_to))
            .group_by(Facility.id, Facility.name)
            .order_by(func.sum(Order.total_amount).desc())
            .limit(limit)
        )
        return [TopFacilityResponse(**row._mapping) for row in result]

    async def recent_orders(self, *, limit: int = 10, date_from: date | None = None, date_to: date | None = None) -> list[RecentOrderResponse]:
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.user), selectinload(Order.facility))
            .where(*self._date_filters(date_from, date_to))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = result.scalars().all()
        return [
            RecentOrderResponse(
                order_id=order.id,
                inmate_id=order.user_id,
                inmate_name=order.user.full_name if order.user else "",
                facility_id=order.facility_id,
                facility_name=order.facility.name if order.facility else "",
                total_amount=order.total_amount,
                status=order.status,
                created_at=order.created_at,
            )
            for order in orders
        ]

    async def low_stock_products(self, *, threshold: int = 10, limit: int = 10) -> list[LowStockProductResponse]:
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.facility),
                selectinload(Product.category),
                selectinload(Product.vendor),
            )
            .where(Product.stock_quantity <= threshold)
            .order_by(Product.stock_quantity.asc(), Product.name.asc())
            .limit(limit)
        )
        products = result.scalars().all()
        return [
            LowStockProductResponse(
                product_id=product.id,
                product_name=product.name,
                facility_id=product.facility_id,
                facility_name=product.facility.name if product.facility else None,
                category_name=product.category.name if product.category else None,
                vendor_name=product.vendor.name if product.vendor else None,
                stock_quantity=product.stock_quantity,
                price=product.price,
                is_active=product.is_active,
            )
            for product in products
        ]

    async def facility_analytics_summary(self, *, date_from: date | None = None, date_to: date | None = None) -> FacilityAnalyticsSummaryResponse:
        filters = [self._active_order_filter(), *self._date_filters(date_from, date_to)]
        total_spent = await self.db.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(*filters)
        )
        facilities_with_orders = await self.db.scalar(
            select(func.count(func.distinct(Order.facility_id))).where(*filters)
        )
        average_order_amount = await self.db.scalar(
            select(func.coalesce(func.avg(Order.total_amount), 0)).where(*filters)
        )
        top_facilities = await self.top_facilities(limit=1, date_from=date_from, date_to=date_to)
        top = top_facilities[0] if top_facilities else None
        return FacilityAnalyticsSummaryResponse(
            total_spent=total_spent or Decimal(0),
            facilities_with_orders=facilities_with_orders or 0,
            average_order_amount=average_order_amount or Decimal(0),
            top_facility_id=top.facility_id if top else None,
            top_facility_name=top.facility_name if top else None,
        )

    async def facilities_analytics_table(self, *, date_from: date | None = None, date_to: date | None = None) -> list[FacilityAnalyticsRowResponse]:
        result = await self.db.execute(select(Facility).where(Facility.is_active == True).order_by(Facility.name))
        facilities = result.scalars().all()
        rows: list[FacilityAnalyticsRowResponse] = []
        for facility in facilities:
            orders_total = await self.db.scalar(
                select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                    Order.facility_id == facility.id,
                    self._active_order_filter(),
                    *self._date_filters(date_from, date_to),
                )
            )
            orders_count = await self.db.scalar(
                select(func.count(Order.id)).where(
                    Order.facility_id == facility.id,
                    self._active_order_filter(),
                    *self._date_filters(date_from, date_to),
                )
            )
            avg_order = await self.db.scalar(
                select(func.coalesce(func.avg(Order.total_amount), 0)).where(
                    Order.facility_id == facility.id,
                    self._active_order_filter(),
                    *self._date_filters(date_from, date_to),
                )
            )
            active_inmates = await self.db.scalar(
                select(func.count(User.id)).where(
                    User.facility_id == facility.id,
                    User.role == UserRole.INMATE,
                    User.is_active == True,
                )
            )
            top_product_row = await self.db.execute(
                select(Product.name)
                .join(OrderItem, OrderItem.product_id == Product.id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.facility_id == facility.id, self._active_order_filter(), *self._date_filters(date_from, date_to))
                .group_by(Product.name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(1)
            )
            top_category_row = await self.db.execute(
                select(Category.name)
                .join(Product, Product.category_id == Category.id)
                .join(OrderItem, OrderItem.product_id == Product.id)
                .join(Order, Order.id == OrderItem.order_id)
                .where(Order.facility_id == facility.id, self._active_order_filter(), *self._date_filters(date_from, date_to))
                .group_by(Category.name)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(1)
            )
            rows.append(
                FacilityAnalyticsRowResponse(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    total_spent=orders_total or Decimal(0),
                    orders_count=orders_count or 0,
                    average_order_amount=avg_order or Decimal(0),
                    active_inmates=active_inmates or 0,
                    top_product=top_product_row.scalar_one_or_none(),
                    top_category=top_category_row.scalar_one_or_none(),
                )
            )
        return rows

    async def facility_trend(self, *, facility_id: UUID | None = None, group_by: str = "month", date_from: date | None = None, date_to: date | None = None) -> list[TimeSeriesPointResponse]:
        date_expr = func.date_trunc(group_by, Order.created_at)
        query = (
            select(
                func.to_char(date_expr, "YYYY-MM-DD").label("period"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_amount"),
            )
            .where(self._active_order_filter(), *self._date_filters(date_from, date_to))
            .group_by(date_expr)
            .order_by(date_expr.asc())
        )
        if facility_id is not None:
            query = query.where(Order.facility_id == facility_id)
        result = await self.db.execute(query)
        return [TimeSeriesPointResponse(period=row.period, total_amount=row.total_amount) for row in result]

    async def facility_detail(self, facility_id: UUID, *, date_from: date | None = None, date_to: date | None = None) -> FacilityDetailAnalyticsResponse:
        facility = await self.db.scalar(select(Facility).where(Facility.id == facility_id))
        if facility is None:
            raise NotFoundError("Учреждение не найдено")
        total_spent = await self.db.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.facility_id == facility_id,
                self._active_order_filter(),
                *self._date_filters(date_from, date_to),
            )
        )
        orders_count = await self.db.scalar(
            select(func.count(Order.id)).where(
                Order.facility_id == facility_id,
                self._active_order_filter(),
                *self._date_filters(date_from, date_to),
            )
        )
        average_order_amount = await self.db.scalar(
            select(func.coalesce(func.avg(Order.total_amount), 0)).where(
                Order.facility_id == facility_id,
                self._active_order_filter(),
                *self._date_filters(date_from, date_to),
            )
        )
        active_inmates = await self.db.scalar(
            select(func.count(User.id)).where(
                User.facility_id == facility_id,
                User.role == UserRole.INMATE,
                User.is_active == True,
            )
        )
        pending_orders = await self.db.scalar(
            select(func.count(Order.id)).where(
                Order.facility_id == facility_id,
                Order.status == OrderStatus.PENDING,
                *self._date_filters(date_from, date_to),
            )
        )
        return FacilityDetailAnalyticsResponse(
            facility_id=facility.id,
            facility_name=facility.name,
            total_spent=total_spent or Decimal(0),
            orders_count=orders_count or 0,
            average_order_amount=average_order_amount or Decimal(0),
            active_inmates=active_inmates or 0,
            pending_orders=pending_orders or 0,
        )

    async def facility_top_products(self, facility_id: UUID, *, limit: int = 10, date_from: date | None = None, date_to: date | None = None) -> list[TopProductResponse]:
        result = await self.db.execute(
            select(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(OrderItem.subtotal), 0).label("total_amount"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.facility_id == facility_id, self._active_order_filter(), *self._date_filters(date_from, date_to))
            .group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.subtotal).desc())
            .limit(limit)
        )
        return [TopProductResponse(**row._mapping) for row in result]
