from fastapi import APIRouter, Depends

from app.dependencies import get_db
from app.services.user_service import UserService
from app.schemas.wallet import WalletResponse, TopUpRequest
from app.services.wallet_service import WalletService
from app.core.security import require_inmate, require_admin

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
            raise AuthorizationError("Cannot top up wallet of user from another facility")
    svc = WalletService(db)
    wallet = await svc.top_up(data.user_id, data.amount)
    return WalletResponse.model_validate(wallet)
