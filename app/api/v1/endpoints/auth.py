from fastapi import APIRouter, Depends

from app.dependencies import get_db, CurrentUserDep
from app.schemas.auth import LoginRequest, Token, RefreshRequest
from app.services.auth_service import AuthService
from app.core.security import get_current_user_dep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, db=Depends(get_db)):
    svc = AuthService(db)
    access, refresh, user_role = await svc.login(data.login, data.password)
    return Token(access_token=access, refresh_token=refresh, user_role=user_role)


@router.post("/refresh", response_model=Token)
async def refresh(data: RefreshRequest, db=Depends(get_db)):
    svc = AuthService(db)
    access, refresh, user_role = await svc.refresh_tokens(data.refresh_token)
    return Token(access_token=access, refresh_token=refresh, user_role=user_role)


@router.get("/me")
async def me(current_user: CurrentUserDep = Depends(get_current_user_dep)):
    from app.schemas.user import UserResponse
    return UserResponse.model_validate(current_user)
