from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.enums import UserRole
from app.dependencies import get_db
from app.schemas.user import UserCreate, UserPhotoUploadResponse, UserUpdate, UserResponse
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


@router.post("/{user_id}/photo", response_model=UserPhotoUploadResponse)
async def upload_inmate_photo(
    user_id: UUID,
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    if not file.filename:
        raise ValidationError("Photo filename is required")
    if file.content_type and not file.content_type.startswith("image/"):
        raise ValidationError("Only image uploads are supported")

    svc = UserService(db)
    user = await svc.get_by_id(user_id)

    if user.role != UserRole.INMATE:
        raise ValidationError("Photo upload is allowed only for inmates")

    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Access denied")

    file_bytes = await file.read()
    storage = MinioStorageService()
    upload_result = storage.upload_object(
        user_id=user.id,
        file_bytes=file_bytes,
        content_type=file.content_type,
        filename=file.filename,
    )

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

    return UserPhotoUploadResponse(
        user_id=updated.id,
        photo_url=updated.photo_url,
        photo_object_key=updated.photo_object_key,
        biometric_enrolled=True,
        biometric_provider=biometric.provider,
    )


@router.post("/{user_id}/photo/re-enroll", response_model=UserPhotoUploadResponse)
async def re_enroll_inmate_photo(
    user_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)

    if user.role != UserRole.INMATE:
        raise ValidationError("Face biometrics can be enrolled only for inmates")
    if not user.photo_object_key or not user.photo_url:
        raise ValidationError("User does not have an uploaded photo")
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Access denied")

    storage = MinioStorageService()
    file_bytes = storage.download_object(user.photo_object_key)
    face_service = FaceBiometricService(db)
    biometric = await face_service.enroll_user_photo(
        user=user,
        photo_object_key=user.photo_object_key,
        file_bytes=file_bytes,
    )

    return UserPhotoUploadResponse(
        user_id=user.id,
        photo_url=user.photo_url,
        photo_object_key=user.photo_object_key,
        biometric_enrolled=True,
        biometric_provider=biometric.provider,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db=Depends(get_db), current_user=Depends(require_admin)):
    svc = UserService(db)
    user = await svc.get_by_id(user_id)
    if current_user.role.value == "PRISON_ADMIN" and current_user.facility_id != user.facility_id:
        raise AuthorizationError("Access denied")
    return _to_user_response(user)


@router.post("", response_model=UserResponse)
async def create_user(data: UserCreate, db=Depends(get_db), current_user=Depends(require_super_admin)):
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
