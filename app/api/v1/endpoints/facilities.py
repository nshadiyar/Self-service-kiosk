from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationError
from app.dependencies import get_db
from app.schemas.facility import FacilityCreate, FacilityUpdate, FacilityResponse
from app.services.facility_service import FacilityService
from app.core.security import get_current_user_dep, require_super_admin

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityResponse])
async def list_facilities(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dep),
):
    if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.PRISON_ADMIN, UserRole.WAREHOUSE_MANAGER}:
        raise AuthorizationError("Доступ запрещен")
    svc = FacilityService(db)
    if current_user.role in {UserRole.PRISON_ADMIN, UserRole.WAREHOUSE_MANAGER} and current_user.facility_id:
        facility = await svc.get_by_id(current_user.facility_id)
        return [FacilityResponse.model_validate(facility)]
    facilities = await svc.list_facilities(skip=skip, limit=limit)
    return [FacilityResponse.model_validate(f) for f in facilities]


@router.get("/{facility_id}", response_model=FacilityResponse)
async def get_facility(facility_id: UUID, db=Depends(get_db), current_user=Depends(get_current_user_dep)):
    if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.PRISON_ADMIN, UserRole.WAREHOUSE_MANAGER}:
        raise AuthorizationError("Доступ запрещен")
    if (
        current_user.role in {UserRole.PRISON_ADMIN, UserRole.WAREHOUSE_MANAGER}
        and current_user.facility_id is not None
        and facility_id != current_user.facility_id
    ):
        raise AuthorizationError("Доступ запрещен")
    svc = FacilityService(db)
    facility = await svc.get_by_id(facility_id)
    return FacilityResponse.model_validate(facility)


@router.post("", response_model=FacilityResponse)
async def create_facility(data: FacilityCreate, db=Depends(get_db), current_user=Depends(require_super_admin)):
    svc = FacilityService(db)
    facility = await svc.create(data)
    return FacilityResponse.model_validate(facility)


@router.patch("/{facility_id}", response_model=FacilityResponse)
async def update_facility(
    facility_id: UUID, data: FacilityUpdate, db=Depends(get_db), current_user=Depends(require_super_admin)
):
    svc = FacilityService(db)
    facility = await svc.update(facility_id, data)
    return FacilityResponse.model_validate(facility)
