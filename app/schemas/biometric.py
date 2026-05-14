from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FaceBiometricResponse(BaseModel):
    id: UUID
    user_id: UUID
    photo_object_key: str
    provider: str
    provider_version: str
    quality_score: float | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FaceAuthAttemptResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    facility_id: UUID | None
    provider: str
    match_score: float | None
    threshold: float | None
    liveness_score: float | None
    success: bool
    failure_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FaceAnalyticsSummary(BaseModel):
    provider: str
    match_threshold: float
    attempts_total: int
    attempts_success: int
    attempts_failed: int
    success_rate: float
    biometrics_total: int
    biometrics_active: int
    average_match_score: float | None
    average_liveness_score: float | None


class FaceTuningConfigResponse(BaseModel):
    provider: str
    match_threshold: float
    match_min_gap: float
    min_blur_variance: float
    hard_min_blur_variance: float
    min_brightness: float
    max_brightness: float
    hard_min_brightness: float
    hard_max_brightness: float
    min_face_area_ratio: float
    min_quality_score: float
    min_eye_count: int
    secondary_face_max_ratio: float


class FaceTuningEvaluationResponse(BaseModel):
    matched_user_id: UUID | None
    match_score: float
    threshold: float
    effective_threshold: float
    second_best_score: float | None
    score_gap: float | None
    quality_score: float
    liveness_score: float | None
    would_authenticate: bool
    provider: str
