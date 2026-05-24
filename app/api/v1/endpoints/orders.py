from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_db
from app.schemas.order import (
    AssignCourierRequest,
    DeliverOrderRequest,
    DeliveryFailureRequest,
    OrderCreate,
    OrderResponse,
    RejectOrderRequest,
)
from app.services.audit_service import AuditService
from app.services.order_service import OrderService
from app.core.security import (
    get_current_user_dep,
    require_admin,
    require_courier,
    require_inmate,
    require_warehouse,
)
from app.core.enums import OrderStatus, UserRole
from app.core.exceptions import AuthorizationError

router = APIRouter(prefix="/orders", tags=["orders"])


def _to_order_response(order) -> OrderResponse:
    user_full_name = order.user.full_name if order.user else None
    courier_name = order.courier.full_name if order.courier else None
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


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: OrderStatus | None = Query(None),
    facility_id: UUID | None = Query(None),
    full_name: str | None = Query(None, description="Поиск по ФИО заключённого"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = OrderService(db)
    user_filter = None
    courier_filter = None
    facility_filter = facility_id
    if current_user.role == UserRole.INMATE:
        user_filter = current_user.id
        facility_filter = current_user.facility_id
    elif current_user.role == UserRole.COURIER:
        courier_filter = current_user.id
        facility_filter = current_user.facility_id
    elif current_user.role in {UserRole.PRISON_ADMIN, UserRole.WAREHOUSE_MANAGER} and current_user.facility_id:
        facility_filter = current_user.facility_id
    orders = await svc.list_orders(
        user_id=user_filter,
        courier_id=courier_filter,
        facility_id=facility_filter,
        status=status,
        full_name=full_name,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [_to_order_response(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.INMATE and order.user_id != current_user.id:
        raise AuthorizationError("Доступ запрещен")
    if current_user.role in {UserRole.PRISON_ADMIN, UserRole.WAREHOUSE_MANAGER} and current_user.facility_id and current_user.facility_id != order.facility_id:
        raise AuthorizationError("Доступ запрещен")
    if current_user.role == UserRole.COURIER and order.courier_id != current_user.id:
        raise AuthorizationError("Доступ запрещен")
    return _to_order_response(order)


@router.post("", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    db=Depends(get_db),
    current_user=Depends(require_inmate),
):
    svc = OrderService(db)
    order = await svc.create(current_user, data)
    return _to_order_response(order)


@router.post("/{order_id}/approve", response_model=OrderResponse)
async def approve_order(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.PRISON_ADMIN and order.facility_id != current_user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.approve(order_id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="APPROVE_ORDER",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Одобрен заказ {order.id}",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/reject", response_model=OrderResponse)
async def reject_order(
    order_id: UUID,
    data: RejectOrderRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.PRISON_ADMIN and order.facility_id != current_user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.reject(order_id, data.reason)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="REJECT_ORDER",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Отклонен заказ {order.id}",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/start-packing", response_model=OrderResponse)
async def start_packing(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_warehouse),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.WAREHOUSE_MANAGER and current_user.facility_id and order.facility_id != current_user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.start_packing(order_id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="START_ORDER_PACKING",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Заказ {order.id} взят в сборку",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/assign-courier", response_model=OrderResponse)
async def assign_courier(
    order_id: UUID,
    data: AssignCourierRequest,
    db=Depends(get_db),
    current_user=Depends(require_warehouse),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.WAREHOUSE_MANAGER and current_user.facility_id and order.facility_id != current_user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.assign_courier(order_id, data.courier_id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="ASSIGN_ORDER_COURIER",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"На заказ {order.id} назначен курьер",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/depart", response_model=OrderResponse)
async def depart_order(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_courier),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.COURIER and order.courier_id != current_user.id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.mark_departed(order_id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="DEPART_ORDER",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Курьер выехал с заказом {order.id}",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/arrive-at-facility", response_model=OrderResponse)
async def arrive_at_facility(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_courier),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.COURIER and order.courier_id != current_user.id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.mark_arrived_at_facility(order_id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="ARRIVE_ORDER_AT_FACILITY",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Курьер прибыл в учреждение с заказом {order.id}",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/deliver", response_model=OrderResponse)
async def deliver_order(
    order_id: UUID,
    data: DeliverOrderRequest,
    db=Depends(get_db),
    current_user=Depends(require_courier),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.COURIER and order.courier_id != current_user.id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.deliver(order_id, data.recipient_employee_name)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="DELIVER_ORDER",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Заказ {order.id} доставлен и передан сотруднику {order.recipient_employee_name}",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)


@router.post("/{order_id}/fail-delivery", response_model=OrderResponse)
async def fail_delivery(
    order_id: UUID,
    data: DeliveryFailureRequest,
    db=Depends(get_db),
    current_user=Depends(require_courier),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role == UserRole.COURIER and order.courier_id != current_user.id:
        raise AuthorizationError("Доступ запрещен")
    order = await svc.fail_delivery(order_id, data.reason)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="FAIL_ORDER_DELIVERY",
        entity_type="order",
        entity_id=str(order.id),
        summary=f"Зафиксирована проблема доставки заказа {order.id}",
        payload_after=_to_order_response(order).model_dump(mode="json"),
    )
    return _to_order_response(order)
