from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.enums import UserRole
from app.dependencies import get_db
from app.schemas.user import (
    InmateCreateWithPhotoResponse,
    UserCreate,
    UserUpdate,
    UserResponse,
)
from app.core.exceptions import AuthorizationError, ValidationError
from app.services.face_biometric_service import FaceBiometricService
from app.services.storage_service import MinioStorageService
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


@router.get("/storage/minio/health")
async def minio_health_check(current_user=Depends(require_admin)):
    storage = MinioStorageService()
    return storage.healthcheck()


async def _store_and_enroll_inmate_photo(*, db, user, file: UploadFile) -> tuple[object, object]:
    if not file.filename:
        raise ValidationError("Photo filename is required")
    if file.content_type and not file.content_type.startswith("image/"):
        raise ValidationError("Only image uploads are supported")

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
    iin: str | None = Form(None),
    transfer_date: str | None = Form(None),
    release_date: str | None = Form(None),
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
            "iin": iin,
            "transfer_date": transfer_date,
            "release_date": release_date,
        }
    )

    svc = UserService(db)
    created = await svc.create(payload)
    user = await svc.get_by_id(created.id)
    updated, biometric = await _store_and_enroll_inmate_photo(db=db, user=user, file=file)
    response_user = await svc.get_by_id(updated.id)

    response = _to_user_response(response_user).model_dump()
    response["biometric_enrolled"] = True
    response["biometric_provider"] = biometric.provider
    return InmateCreateWithPhotoResponse(**response)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db=Depends(get_db), current_user=Depends(require_admin)):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Access denied")
    return _to_user_response(user)


@router.post("", response_model=UserResponse)
async def create_user(data: UserCreate, db=Depends(get_db), current_user=Depends(require_super_admin)):
    if data.role == UserRole.INMATE:
        raise ValidationError("Use /api/v1/users/inmates/with-photo to create inmates")
    svc = UserService(db)
    created = await svc.create(data)
    user = await svc.get_by_id(created.id)
    return _to_user_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: UUID, data: UserUpdate, db=Depends(get_db), current_user=Depends(require_admin)):
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id:
        svc = UserService(db)
        user = await svc.get_by_id(user_id)
        if user.facility_id != current_user.facility_id:
            raise AuthorizationError("Access denied")
    svc = UserService(db)
    updated = await svc.update(user_id, data)
    user = await svc.get_by_id(updated.id)
    return _to_user_response(user)
