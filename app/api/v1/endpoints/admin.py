from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.enums import OrderStatus
from app.core.exceptions import NotFoundError
from app.core.security import require_super_admin
from app.dependencies import get_db
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
from app.schemas.audit import AuditLogResponse
from app.schemas.order import OrderResponse
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.order_service import OrderService
from app.services.user_service import UserService
from app.services.wallet_service import WalletService
from app.core.enums import UserRole
from app.schemas.wallet import WalletResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_order_response(order) -> OrderResponse:
    user_full_name = order.user.full_name if order.user else None
    courier_name = order.courier.full_name if getattr(order, "courier", None) else None
    facility_name = order.facility.name if order.facility else None
    payload = OrderResponse.model_validate(order).model_dump()
    payload["user_full_name"] = user_full_name
    payload["courier_name"] = courier_name
    payload["facility_name"] = facility_name
    payload["items"] = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else None,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
        }
        for item in order.items
    ]
    return OrderResponse(**payload)


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.dashboard_summary(date_from=date_from, date_to=date_to)


@router.get("/dashboard/spending-trend", response_model=list[TimeSeriesPointResponse])
async def dashboard_spending_trend(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.spending_trend(group_by=group_by, date_from=date_from, date_to=date_to)


@router.get("/dashboard/orders-by-status", response_model=list[StatusCountResponse])
async def dashboard_orders_by_status(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.orders_by_status(date_from=date_from, date_to=date_to)


@router.get("/dashboard/top-products", response_model=list[TopProductResponse])
async def dashboard_top_products(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(5, ge=1, le=50),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.top_products(limit=limit, date_from=date_from, date_to=date_to)


@router.get("/dashboard/top-facilities", response_model=list[TopFacilityResponse])
async def dashboard_top_facilities(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(5, ge=1, le=50),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.top_facilities(limit=limit, date_from=date_from, date_to=date_to)


@router.get("/dashboard/recent-orders", response_model=list[RecentOrderResponse])
async def dashboard_recent_orders(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.recent_orders(limit=limit, date_from=date_from, date_to=date_to)


@router.get("/dashboard/low-stock-products", response_model=list[LowStockProductResponse])
async def dashboard_low_stock_products(
    threshold: int = Query(10, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.low_stock_products(threshold=threshold, limit=limit)


@router.get("/facilities/analytics/summary", response_model=FacilityAnalyticsSummaryResponse)
async def facilities_analytics_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.facility_analytics_summary(date_from=date_from, date_to=date_to)


@router.get("/facilities/analytics/table", response_model=list[FacilityAnalyticsRowResponse])
async def facilities_analytics_table(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.facilities_analytics_table(date_from=date_from, date_to=date_to)


@router.get("/facilities/analytics/spending-chart", response_model=list[TopFacilityResponse])
async def facilities_spending_chart(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.top_facilities(limit=limit, date_from=date_from, date_to=date_to)


@router.get("/facilities/analytics/trend", response_model=list[TimeSeriesPointResponse])
async def facilities_trend(
    facility_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    group_by: str = Query("month", pattern="^(day|week|month)$"),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.facility_trend(
        facility_id=facility_id,
        group_by=group_by,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/facilities/{facility_id}/analytics", response_model=FacilityDetailAnalyticsResponse)
async def facility_detail_analytics(
    facility_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.facility_detail(facility_id, date_from=date_from, date_to=date_to)


@router.get("/facilities/{facility_id}/top-products", response_model=list[TopProductResponse])
async def facility_top_products(
    facility_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AdminService(db)
    return await svc.facility_top_products(facility_id, limit=limit, date_from=date_from, date_to=date_to)


@router.get("/facilities/{facility_id}/orders", response_model=list[OrderResponse])
async def facility_orders(
    facility_id: UUID,
    status: OrderStatus | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    order_svc = OrderService(db)
    orders = await order_svc.list_orders(
        facility_id=facility_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [_to_order_response(order) for order in orders]


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def list_audit_log(
    actor_user_id: UUID | None = Query(None),
    actor_role: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AuditService(db)
    return await svc.list_events(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )


@router.get("/audit-log/{event_id}", response_model=AuditLogResponse)
async def get_audit_log_event(
    event_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = AuditService(db)
    event = await svc.get_event(event_id)
    if event is None:
        raise NotFoundError("Запись аудита не найдена")
    return event


@router.get("/inmates/{user_id}/orders", response_model=list[OrderResponse])
async def admin_inmate_orders(
    user_id: UUID,
    status: OrderStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    user_svc = UserService(db)
    user = await user_svc.get_by_id(user_id)
    if user.role != UserRole.INMATE:
        raise NotFoundError("Заключенный не найден")
    order_svc = OrderService(db)
    orders = await order_svc.list_orders(user_id=user_id, status=status, skip=skip, limit=limit)
    return [_to_order_response(order) for order in orders]


@router.get("/inmates/{user_id}/wallet", response_model=WalletResponse)
async def admin_inmate_wallet(
    user_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    user_svc = UserService(db)
    user = await user_svc.get_by_id(user_id)
    if user.role != UserRole.INMATE:
        raise NotFoundError("Заключенный не найден")
    wallet_svc = WalletService(db)
    wallet = await wallet_svc.get_by_user_id(user_id)
    return WalletResponse.model_validate(wallet)
