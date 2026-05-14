from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select

from app.config import settings
from app.core.enums import UserRole
from app.core.exceptions import ValidationError
from app.core.security import require_admin
from app.dependencies import get_db
from app.models.face_auth_attempt import FaceAuthAttempt
from app.models.face_biometric import FaceBiometric
from app.models.user import User
from app.schemas.biometric import (
    FaceAnalyticsSummary,
    FaceAuthAttemptResponse,
    FaceBiometricResponse,
    FaceTuningConfigResponse,
    FaceTuningEvaluationResponse,
)
from app.services.face_biometric_service import FaceBiometricService
from app.services.storage_service import MinioStorageService
from app.services.user_service import UserService

router = APIRouter(prefix="/biometrics", tags=["biometrics"])


@router.get("/config", response_model=FaceTuningConfigResponse)
async def get_face_config(current_user=Depends(require_admin)):
    return FaceTuningConfigResponse(
        provider=settings.face_provider_name,
        match_threshold=settings.face_match_threshold,
        match_min_gap=settings.face_match_min_gap,
        min_blur_variance=settings.face_login_min_blur_variance,
        hard_min_blur_variance=settings.face_login_hard_min_blur_variance,
        min_brightness=settings.face_login_min_brightness,
        max_brightness=settings.face_login_max_brightness,
        hard_min_brightness=settings.face_login_hard_min_brightness,
        hard_max_brightness=settings.face_login_hard_max_brightness,
        min_face_area_ratio=settings.face_login_min_face_area_ratio,
        min_quality_score=settings.face_login_min_quality_score,
        min_eye_count=settings.face_login_min_eye_count,
        secondary_face_max_ratio=settings.face_login_secondary_face_max_ratio,
    )


@router.get("/analytics/summary", response_model=FaceAnalyticsSummary)
async def face_analytics_summary(db=Depends(get_db), current_user=Depends(require_admin)):
    attempts_total = (await db.execute(select(func.count(FaceAuthAttempt.id)))).scalar_one()
    attempts_success = (
        await db.execute(select(func.count(FaceAuthAttempt.id)).where(FaceAuthAttempt.success == True))
    ).scalar_one()
    attempts_failed = attempts_total - attempts_success
    biometrics_total = (await db.execute(select(func.count(FaceBiometric.id)))).scalar_one()
    biometrics_active = (
        await db.execute(select(func.count(FaceBiometric.id)).where(FaceBiometric.is_active == True))
    ).scalar_one()
    average_match_score = (await db.execute(select(func.avg(FaceAuthAttempt.match_score)))).scalar_one()
    average_liveness_score = (await db.execute(select(func.avg(FaceAuthAttempt.liveness_score)))).scalar_one()

    success_rate = round((attempts_success / attempts_total), 4) if attempts_total else 0.0
    return FaceAnalyticsSummary(
        provider=settings.face_provider_name,
        match_threshold=settings.face_match_threshold,
        attempts_total=attempts_total,
        attempts_success=attempts_success,
        attempts_failed=attempts_failed,
        success_rate=success_rate,
        biometrics_total=biometrics_total,
        biometrics_active=biometrics_active,
        average_match_score=float(average_match_score) if average_match_score is not None else None,
        average_liveness_score=float(average_liveness_score) if average_liveness_score is not None else None,
    )


@router.get("/records", response_model=list[FaceBiometricResponse])
async def list_biometric_records(
    user_id: UUID | None = Query(None),
    active_only: bool = Query(True),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    query = select(FaceBiometric).order_by(FaceBiometric.created_at.desc())
    if user_id is not None:
        query = query.where(FaceBiometric.user_id == user_id)
    if active_only:
        query = query.where(FaceBiometric.is_active == True)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/attempts", response_model=list[FaceAuthAttemptResponse])
async def list_face_attempts(
    user_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    query = select(FaceAuthAttempt).order_by(FaceAuthAttempt.created_at.desc()).limit(limit)
    if user_id is not None:
        query = query.where(FaceAuthAttempt.user_id == user_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.delete("/records/{biometric_id}", response_model=FaceBiometricResponse)
async def deactivate_biometric_record(
    biometric_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    result = await db.execute(select(FaceBiometric).where(FaceBiometric.id == biometric_id))
    biometric = result.scalar_one_or_none()
    if not biometric:
        raise ValidationError("Biometric record not found")
    biometric.is_active = False
    await db.flush()
    await db.refresh(biometric)
    return biometric


@router.post("/tuning/evaluate", response_model=FaceTuningEvaluationResponse)
async def evaluate_face_tuning(
    facility_id: UUID | None = Form(None),
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user=Depends(require_admin),
):
    if file.content_type and not file.content_type.startswith("image/"):
        raise ValidationError("Only image uploads are supported")
    face_service = FaceBiometricService(db)
    sample = face_service._extract_face_sample(await file.read(), enforce_liveness=True)

    query = (
        select(FaceBiometric)
        .join(FaceBiometric.user)
        .where(FaceBiometric.is_active == True, User.is_active == True, User.role == UserRole.INMATE)
    )
    if facility_id is not None:
        query = query.where(User.facility_id == facility_id)
    result = await db.execute(query)
    biometrics = list(result.scalars().all())

    evaluation = face_service.evaluate_candidates(sample=sample, biometrics=biometrics)

    return FaceTuningEvaluationResponse(
        matched_user_id=evaluation["matched_user_id"],
        match_score=evaluation["match_score"],
        threshold=settings.face_match_threshold,
        effective_threshold=evaluation["effective_threshold"],
        second_best_score=evaluation["second_best_score"],
        score_gap=evaluation["score_gap"],
        quality_score=sample.quality_score,
        liveness_score=sample.liveness_score,
        would_authenticate=evaluation["would_authenticate"],
        provider=settings.face_provider_name,
    )
