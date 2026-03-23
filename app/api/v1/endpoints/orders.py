from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_db
from app.schemas.order import OrderCreate, OrderResponse, RejectOrderRequest
from app.services.order_service import OrderService
from app.core.security import get_current_user_dep, require_admin, require_inmate
from app.core.enums import OrderStatus

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: OrderStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = OrderService(db)
    user_filter = None
    facility_filter = None
    if current_user.role.value == "INMATE":
        user_filter = current_user.id
    elif current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        facility_filter = current_user.facility_id
    orders = await svc.list_orders(user_id=user_filter, facility_id=facility_filter, status=status, skip=skip, limit=limit)
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role.value == "INMATE" and order.user_id != current_user.id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Access denied")
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != order.facility_id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Access denied")
    return OrderResponse.model_validate(order)


@router.post("", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    db=Depends(get_db),
    current_user=Depends(require_inmate),
):
    svc = OrderService(db)
    order = await svc.create(current_user, data)
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/approve", response_model=OrderResponse)
async def approve_order(
    order_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role.value == "PRISON_ADMIN" and order.facility_id != current_user.facility_id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Access denied")
    order = await svc.approve(order_id)
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/reject", response_model=OrderResponse)
async def reject_order(
    order_id: UUID,
    data: RejectOrderRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if current_user.role.value == "PRISON_ADMIN" and order.facility_id != current_user.facility_id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Access denied")
    order = await svc.reject(order_id, data.reason)
    return OrderResponse.model_validate(order)
