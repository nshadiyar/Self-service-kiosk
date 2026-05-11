from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies import get_db, CurrentUserDep
from app.schemas.auth import FaceLoginResponse, LoginRequest, Token, RefreshRequest
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


@router.post("/face-login", response_model=FaceLoginResponse)
async def face_login(
    facility_id: UUID | None = Form(None),
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    if not file.filename:
        from app.core.exceptions import ValidationError
        raise ValidationError("Photo filename is required")
    if file.content_type and not file.content_type.startswith("image/"):
        from app.core.exceptions import ValidationError
        raise ValidationError("Only image uploads are supported")

    svc = AuthService(db)
    file_bytes = await file.read()
    access, refresh, user_role, matched_user_id, match_score, provider = await svc.face_login(
        file_bytes=file_bytes,
        facility_id=facility_id,
    )
    return FaceLoginResponse(
        access_token=access,
        refresh_token=refresh,
        user_role=user_role,
        matched_user_id=matched_user_id,
        match_score=match_score,
        provider=provider,
    )


@router.get("/me")
async def me(current_user: CurrentUserDep = Depends(get_current_user_dep)):
    from app.schemas.user import UserResponse
    return UserResponse.model_validate(current_user)
