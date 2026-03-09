from fastapi import APIRouter, Depends, Query

from app.dependencies import get_db
from app.schemas.facility import FacilityCreate, FacilityUpdate, FacilityResponse
from app.services.facility_service import FacilityService
from app.core.security import require_super_admin, require_admin

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityResponse])
async def list_facilities(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = FacilityService(db)
    facilities = await svc.list_facilities(skip=skip, limit=limit)
    return [FacilityResponse.model_validate(f) for f in facilities]


@router.get("/{facility_id}", response_model=FacilityResponse)
async def get_facility(facility_id: int, db=Depends(get_db), current_user=Depends(require_admin)):
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
    facility_id: int, data: FacilityUpdate, db=Depends(get_db), current_user=Depends(require_super_admin)
):
    svc = FacilityService(db)
    facility = await svc.update(facility_id, data)
    return FacilityResponse.model_validate(facility)
