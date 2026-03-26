from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.enums import UserRole
from app.dependencies import get_db
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService
from app.core.security import require_admin, require_super_admin

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_response(user) -> UserResponse:
    facility_name = user.facility.name if user.facility else None
    payload = UserResponse.model_validate(user).model_dump()
    payload["facility_name"] = facility_name
    return UserResponse(**payload)


@router.get("", response_model=list[UserResponse])
async def list_users(
    facility_id: UUID | None = Query(None),
    role: UserRole | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    facility_filter = None
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        facility_filter = current_user.facility_id
    elif facility_id is not None:
        facility_filter = facility_id
    svc = UserService(db)
    users = await svc.list_users(facility_id=facility_filter, role=role, skip=skip, limit=limit)
    return [_to_user_response(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db=Depends(get_db), current_user=Depends(require_admin)):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        from app.core.exceptions import AuthorizationError
        raise AuthorizationError("Access denied")
    return _to_user_response(user)


@router.post("", response_model=UserResponse)
async def create_user(data: UserCreate, db=Depends(get_db), current_user=Depends(require_super_admin)):
    svc = UserService(db)
    user = await svc.create(data)
    return _to_user_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: UUID, data: UserUpdate, db=Depends(get_db), current_user=Depends(require_admin)):
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        from app.core.exceptions import AuthorizationError
        svc = UserService(db)
        user = await svc.get_by_id(user_id)
        if user.facility_id != current_user.facility_id:
            raise AuthorizationError("Access denied")
    svc = UserService(db)
    user = await svc.update(user_id, data)
    return _to_user_response(user)
