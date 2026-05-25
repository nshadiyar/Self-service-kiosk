from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.dependencies import get_db
from app.services.user_service import UserService
from app.schemas.wallet import (
    InmateWalletResponse,
    SecurityRegimeLimitResponse,
    SecurityRegimeLimitUpdate,
    TopUpRequest,
    WalletResponse,
)
from app.services.audit_service import AuditService
from app.services.wallet_service import WalletService
from app.core.security import require_admin, require_inmate, require_super_admin

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletResponse)
async def get_wallet(
    db=Depends(get_db),
    current_user=Depends(require_inmate),
):
    svc = WalletService(db)
    wallet = await svc.get_by_user_id(current_user.id)
    return WalletResponse.model_validate(wallet)


@router.post("/top-up", response_model=WalletResponse)
async def top_up(
    data: TopUpRequest,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    from app.core.exceptions import AuthorizationError
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        user_svc = UserService(db)
        user = await user_svc.get_by_id(data.user_id)
        if user.facility_id != current_user.facility_id:
            raise AuthorizationError("Нельзя пополнять кошелек пользователя из другого учреждения")

    svc = WalletService(db)
    wallet = await svc.top_up(data.user_id, data.amount)
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="TOP_UP_WALLET",
        entity_type="wallet",
        entity_id=str(wallet.id),
        summary=f"Пополнен кошелек пользователя {data.user_id}",
        payload_after={"user_id": str(data.user_id), "amount": float(data.amount)},
    )
    wallet_payload = WalletResponse.model_validate(wallet).model_dump(mode="json")
    monthly_limit = wallet_payload.get("monthly_limit")
    return JSONResponse(
        content={
            "success": True,
            "data": wallet_payload,
            "message": f"Кошелек пополнен. Месячный лимит заключенного: {monthly_limit} ₸",
        }
    )


@router.get("/inmates", response_model=list[InmateWalletResponse])
async def list_inmate_wallets(
    facility_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    facility_filter = facility_id
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        facility_filter = current_user.facility_id
    svc = WalletService(db)
    return await svc.list_inmate_wallets(
        facility_id=facility_filter,
        skip=skip,
        limit=limit,
    )


@router.get("/monthly-limits/by-security-regime", response_model=list[SecurityRegimeLimitResponse])
async def list_security_regime_limits(
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = WalletService(db)
    return await svc.list_security_regime_limits()


@router.patch("/monthly-limits/by-security-regime", response_model=SecurityRegimeLimitResponse)
async def update_security_regime_limit(
    data: SecurityRegimeLimitUpdate,
    db=Depends(get_db),
    current_user=Depends(require_super_admin),
):
    svc = WalletService(db)
    result = await svc.upsert_security_regime_limit(
        security_regime=data.security_regime,
        monthly_limit=data.monthly_limit,
    )
    audit = AuditService(db)
    await audit.log_event(
        actor=current_user,
        action="UPDATE_SECURITY_REGIME_LIMIT",
        entity_type="security_regime_limit",
        entity_id=data.security_regime.value,
        summary=f"Изменен месячный лимит для режима {data.security_regime.value}",
        payload_after={"security_regime": data.security_regime.value, "monthly_limit": float(data.monthly_limit)},
    )
    return result
