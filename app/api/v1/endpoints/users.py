from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.enums import OrderStatus, SecurityRegime, UserRole
from app.dependencies import get_db
from app.schemas.user import (
    InmateCreateWithPhotoResponse,
    InmateSettingsUpdate,
    UserCreate,
    UserUpdate,
    UserResponse,
)
from app.core.exceptions import AuthorizationError, ValidationError
from app.services.face_biometric_service import FaceBiometricService
from app.services.order_service import OrderService
from app.services.storage_service import MinioStorageService
from app.services.user_service import UserService
from app.services.wallet_service import WalletService
from app.services.audit_service import AuditService
from app.core.security import get_current_user_dep, require_admin, require_super_admin
from app.schemas.order import OrderResponse
from app.schemas.wallet import WalletResponse

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_response(user) -> UserResponse:
    facility_name = user.facility.name if user.facility else None
    payload = UserResponse.model_validate(user).model_dump()
    payload["facility_name"] = facility_name
    payload["monthly_limit"] = user.wallet.monthly_limit if getattr(user, "wallet", None) else None
    return UserResponse(**payload)


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


@router.get("", response_model=list[UserResponse])
async def list_users(
    facility_id: UUID | None = Query(None),
    role: UserRole | None = Query(None),
    security_regime: SecurityRegime | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        if role != UserRole.COURIER:
            raise AuthorizationError("Начальник склада может просматривать только курьеров")
    elif current_user.role not in {UserRole.SUPER_ADMIN, UserRole.PRISON_ADMIN}:
        raise AuthorizationError("Доступ запрещен")

    facility_filter = None
    if current_user.role == UserRole.WAREHOUSE_MANAGER and current_user.facility_id:
        facility_filter = current_user.facility_id
    elif current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        facility_filter = current_user.facility_id
    elif facility_id is not None:
        facility_filter = facility_id
    svc = UserService(db)
    users = await svc.list_users(
        facility_id=facility_filter,
        role=role,
        security_regime=security_regime,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
    )
    return [_to_user_response(u) for u in users]


@router.get("/storage/minio/health")
async def minio_health_check(current_user=Depends(require_admin)):
    storage = MinioStorageService()
    return storage.healthcheck()


async def _store_and_enroll_inmate_photo(*, db, user, file: UploadFile) -> tuple[object, object]:
    if not file.filename:
        raise ValidationError("Необходимо указать имя файла фотографии")
    if file.content_type and not file.content_type.startswith("image/"):
        raise ValidationError("Поддерживается загрузка только изображений")

    file_bytes = await file.read()
    storage = MinioStorageService()
    upload_result = storage.upload_object(
        user_id=user.id,
        file_bytes=file_bytes,
        content_type=file.content_type,
        filename=file.filename,
    )
    try:
        svc = UserService(db)
        updated = await svc.update_photo(
            user.id,
            photo_url=upload_result["url"],
            photo_object_key=upload_result["object_key"],
        )
        face_service = FaceBiometricService(db)
        biometric = await face_service.enroll_user_photo(
            user=updated,
            photo_object_key=upload_result["object_key"],
            file_bytes=file_bytes,
        )
        return updated, biometric
    except Exception:
        storage.delete_object(upload_result["object_key"])
        raise


@router.post("/inmates/with-photo", response_model=InmateCreateWithPhotoResponse)
async def create_inmate_with_photo(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    facility_id: UUID | None = Form(None),
    security_regime: SecurityRegime = Form(SecurityRegime.GENERAL),
    iin: str | None = Form(None),
    transfer_date: str | None = Form(None),
    release_date: str | None = Form(None),
    monthly_limit: Decimal | None = Form(None, ge=0),
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    payload = UserCreate.model_validate(
        {
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": UserRole.INMATE,
            "facility_id": facility_id,
            "security_regime": security_regime,
            "iin": iin,
            "transfer_date": transfer_date,
            "release_date": release_date,
        }
    )

    svc = UserService(db)
    created = await svc.create(payload)
    if monthly_limit is not None:
        wallet_svc = WalletService(db)
        await wallet_svc.update_monthly_limit(created.id, monthly_limit)
    user = await svc.get_by_id(created.id)
    updated, biometric = await _store_and_enroll_inmate_photo(db=db, user=user, file=file)
    response_user = await svc.get_by_id(updated.id)
    response_model = _to_user_response(response_user)
    response = response_model.model_dump()
    response["biometric_enrolled"] = True
    response["biometric_provider"] = biometric.provider
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="CREATE_INMATE",
        entity_type="user",
        entity_id=str(response_user.id),
        summary=f"Создан заключенный {response_user.full_name}",
        payload_after=InmateCreateWithPhotoResponse(**response).model_dump(mode="json"),
    )
    return InmateCreateWithPhotoResponse(**response)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db=Depends(get_db), current_user=Depends(require_admin)):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    return _to_user_response(user)


@router.get("/{user_id}/orders", response_model=list[OrderResponse])
async def get_inmate_orders(
    user_id: UUID,
    status: OrderStatus | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if user.role != UserRole.INMATE:
        raise ValidationError("Пользователь не является заключенным")
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    order_svc = OrderService(db)
    orders = await order_svc.list_orders(
        user_id=user_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return [_to_order_response(order) for order in orders]


@router.get("/{user_id}/wallet", response_model=WalletResponse)
async def get_inmate_wallet(
    user_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if user.role != UserRole.INMATE:
        raise ValidationError("Пользователь не является заключенным")
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Доступ запрещен")
    wallet_svc = WalletService(db)
    wallet = await wallet_svc.get_by_user_id(user_id)
    return WalletResponse.model_validate(wallet)


@router.post("", response_model=UserResponse)
async def create_user(data: UserCreate, db=Depends(get_db), current_user=Depends(require_super_admin)):
    if data.role == UserRole.INMATE:
        raise ValidationError("Для создания заключенных используйте /api/v1/users/inmates/with-photo")
    svc = UserService(db)
    created = await svc.create(data)
    user = await svc.get_by_id(created.id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="CREATE_USER",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"Создан пользователь {user.full_name}",
        payload_after=_to_user_response(user).model_dump(mode="json"),
    )
    return _to_user_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: UUID, data: UserUpdate, db=Depends(get_db), current_user=Depends(require_admin)):
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        svc = UserService(db)
        user = await svc.get_by_id(user_id)
        if user.facility_id != current_user.facility_id:
            raise AuthorizationError("Доступ запрещен")
    svc = UserService(db)
    before = await svc.get_by_id(user_id)
    before_payload = _to_user_response(before).model_dump(mode="json")
    updated = await svc.update(user_id, data)
    user = await svc.get_by_id(updated.id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="UPDATE_USER",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"Обновлен пользователь {user.full_name}",
        payload_before=before_payload,
        payload_after=_to_user_response(user).model_dump(mode="json"),
    )
    return _to_user_response(user)


@router.patch("/{user_id}/inmate-settings", response_model=UserResponse)
async def update_inmate_settings(
    user_id: UUID,
    data: InmateSettingsUpdate,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if user.role != UserRole.INMATE:
        raise ValidationError("Пользователь не является заключенным")
    before_payload = _to_user_response(user).model_dump(mode="json")

    if "security_regime" in data.model_fields_set and data.security_regime is not None:
        user.security_regime = data.security_regime.value

    if "monthly_limit" in data.model_fields_set:
        wallet_svc = WalletService(db)
        await wallet_svc.update_monthly_limit(user.id, data.monthly_limit)
    elif "security_regime" in data.model_fields_set and data.security_regime is not None:
        wallet_svc = WalletService(db)
        regime_limit = await wallet_svc.get_monthly_limit_for_regime(data.security_regime)
        await wallet_svc.update_monthly_limit(user.id, regime_limit)

    await db.flush()
    refreshed = await svc.get_by_id(user.id)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="UPDATE_INMATE_SETTINGS",
        entity_type="user",
        entity_id=str(refreshed.id),
        summary=f"Обновлены настройки заключенного {refreshed.full_name}",
        payload_before=before_payload,
        payload_after=_to_user_response(refreshed).model_dump(mode="json"),
    )
    return _to_user_response(refreshed)
