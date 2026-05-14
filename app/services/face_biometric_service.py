import json
import logging
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.enums import UserRole
from app.core.exceptions import AuthenticationError, ValidationError
from app.models.face_auth_attempt import FaceAuthAttempt
from app.models.face_biometric import FaceBiometric
from app.models.user import User
from app.schemas.auth import FaceClientMetadata

logger = logging.getLogger(__name__)


@dataclass
class FaceFeatureSample:
    descriptor: np.ndarray
    quality_score: float
    liveness_score: float | None
    blur_variance: float
    brightness: float
    face_area_ratio: float
    eye_count: int
    detected_face_count: int


@dataclass
class FaceMatchEvaluation:
    matched_user_id: UUID | None
    best_biometric: FaceBiometric | None
    match_score: float
    effective_threshold: float
    second_best_score: float | None
    score_gap: float | None
    would_authenticate: bool
    failure_reason: str | None


class FaceBiometricService:
    _analysis_app: FaceAnalysis | None = None

    def __init__(self, db: AsyncSession):
        self.db = db
        self._ensure_model_loaded()

    @classmethod
    def _ensure_model_loaded(cls) -> None:
        if cls._analysis_app is not None:
            return
        try:
            app = FaceAnalysis(
                name=settings.face_model_name,
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=0, det_size=(640, 640))
            cls._analysis_app = app
        except Exception as exc:
            raise ValidationError(f"Face model initialization failed: {exc}") from exc

    async def enroll_user_photo(self, *, user: User, photo_object_key: str, file_bytes: bytes) -> FaceBiometric:
        if user.role != UserRole.INMATE:
            raise ValidationError("Face biometrics can be enrolled only for inmates")

        sample = self._extract_face_sample(file_bytes, enforce_liveness=False)

        result = await self.db.execute(
            select(FaceBiometric).where(FaceBiometric.user_id == user.id, FaceBiometric.is_active == True)
        )
        active_records = list(result.scalars().all())
        for record in active_records:
            record.is_active = False

        biometric = FaceBiometric(
            user_id=user.id,
            photo_object_key=photo_object_key,
            face_signature=json.dumps(sample.descriptor.tolist()),
            provider=settings.face_provider_name,
            provider_version="1",
            quality_score=sample.quality_score,
            is_active=True,
        )
        self.db.add(biometric)
        await self.db.flush()
        await self.db.refresh(biometric)
        return biometric

    async def authenticate(
        self,
        *,
        file_bytes: bytes,
        facility_id: UUID | None,
        client_metadata: FaceClientMetadata | None = None,
    ) -> tuple[User, float]:
        sample = self._extract_face_sample(file_bytes, enforce_liveness=True)

        query = (
            select(FaceBiometric)
            .join(FaceBiometric.user)
            .options(selectinload(FaceBiometric.user))
            .where(FaceBiometric.is_active == True, User.is_active == True, User.role == UserRole.INMATE)
        )
        if facility_id is not None:
            query = query.where(User.facility_id == facility_id)

        result = await self.db.execute(query)
        biometrics = list(result.scalars().all())

        if not biometrics:
            await self._log_attempt(
                user_id=None,
                facility_id=facility_id,
                score=None,
                effective_threshold=None,
                second_best_score=None,
                score_gap=None,
                quality_score=sample.quality_score,
                liveness_score=sample.liveness_score,
                blur_variance=sample.blur_variance,
                brightness=sample.brightness,
                face_area_ratio=sample.face_area_ratio,
                eye_count=sample.eye_count,
                client_metadata=client_metadata,
                success=False,
                failure_reason="No enrolled face biometrics found",
            )
            raise AuthenticationError("Пользователь не найден")

        evaluation = self.evaluate_candidates(sample=sample, biometrics=biometrics)

        if (
            evaluation.matched_user_id is None
            or not evaluation.would_authenticate
            or evaluation.best_biometric is None
        ):
            await self._log_attempt(
                user_id=None,
                facility_id=facility_id,
                score=evaluation.match_score if evaluation.match_score >= 0 else None,
                effective_threshold=evaluation.effective_threshold,
                second_best_score=evaluation.second_best_score,
                score_gap=evaluation.score_gap,
                quality_score=sample.quality_score,
                liveness_score=sample.liveness_score,
                blur_variance=sample.blur_variance,
                brightness=sample.brightness,
                face_area_ratio=sample.face_area_ratio,
                eye_count=sample.eye_count,
                client_metadata=client_metadata,
                success=False,
                failure_reason=evaluation.failure_reason,
            )
            raise AuthenticationError("Пользователь не найден")

        await self._log_attempt(
            user_id=evaluation.matched_user_id,
            facility_id=facility_id,
            score=evaluation.match_score,
            effective_threshold=evaluation.effective_threshold,
            second_best_score=evaluation.second_best_score,
            score_gap=evaluation.score_gap,
            quality_score=sample.quality_score,
            liveness_score=sample.liveness_score,
            blur_variance=sample.blur_variance,
            brightness=sample.brightness,
            face_area_ratio=sample.face_area_ratio,
            eye_count=sample.eye_count,
            client_metadata=client_metadata,
            success=True,
            failure_reason=None,
        )
        return evaluation.best_biometric.user, evaluation.match_score

    def evaluate_candidates(self, *, sample: FaceFeatureSample, biometrics: list[FaceBiometric]) -> FaceMatchEvaluation:
        best_by_user: dict[UUID, tuple[FaceBiometric, float]] = {}
        for biometric in biometrics:
            descriptor = np.asarray(json.loads(biometric.face_signature), dtype=np.float32)
            score = self._cosine_similarity(sample.descriptor, descriptor)
            current = best_by_user.get(biometric.user_id)
            if current is None or score > current[1]:
                best_by_user[biometric.user_id] = (biometric, score)

        scored = sorted(best_by_user.values(), key=lambda item: item[1], reverse=True)
        best_biometric = scored[0][0] if scored else None
        best_score = scored[0][1] if scored else -1.0
        second_best_score = scored[1][1] if len(scored) > 1 else None
        score_gap = None if second_best_score is None else best_score - second_best_score
        effective_threshold = self._effective_match_threshold(
            quality_score=sample.quality_score,
            liveness_score=sample.liveness_score,
        )

        failure_reason = None
        would_authenticate = True
        if best_biometric is None or best_score < effective_threshold:
            would_authenticate = False
            failure_reason = "Face match threshold not reached"
        elif (
            score_gap is not None
            and best_score < settings.face_match_gap_bypass_score
            and score_gap < settings.face_match_min_gap
        ):
            would_authenticate = False
            failure_reason = "Face match is ambiguous"

        logger.info(
            "MATCH DEBUG: score=%.4f, threshold=%.4f, effective_threshold=%.4f, "
            "second_best=%s, gap=%s, min_gap=%.4f, gap_bypass_score=%.4f, "
            "quality=%.4f, liveness=%s, decision=%s, reason=%s",
            best_score,
            settings.face_match_threshold,
            effective_threshold,
            f"{second_best_score:.4f}" if second_best_score is not None else "None",
            f"{score_gap:.4f}" if score_gap is not None else "None",
            settings.face_match_min_gap,
            settings.face_match_gap_bypass_score,
            sample.quality_score,
            f"{sample.liveness_score:.4f}" if sample.liveness_score is not None else "None",
            "allow" if would_authenticate else "deny",
            failure_reason or "matched",
        )

        return FaceMatchEvaluation(
            matched_user_id=best_biometric.user_id if would_authenticate and best_biometric else None,
            best_biometric=best_biometric if would_authenticate else None,
            match_score=best_score,
            effective_threshold=effective_threshold,
            second_best_score=second_best_score,
            score_gap=score_gap,
            would_authenticate=would_authenticate,
            failure_reason=failure_reason,
        )

    async def _log_attempt(
        self,
        *,
        user_id: UUID | None,
        facility_id: UUID | None,
        score: float | None,
        effective_threshold: float | None,
        second_best_score: float | None,
        score_gap: float | None,
        quality_score: float | None,
        liveness_score: float | None,
        blur_variance: float | None,
        brightness: float | None,
        face_area_ratio: float | None,
        eye_count: int | None,
        client_metadata: FaceClientMetadata | None,
        success: bool,
        failure_reason: str | None,
    ) -> None:
        attempt = FaceAuthAttempt(
            user_id=user_id,
            facility_id=facility_id,
            provider=settings.face_provider_name,
            match_score=score,
            threshold=settings.face_match_threshold,
            effective_threshold=effective_threshold,
            second_best_score=second_best_score,
            score_gap=score_gap,
            quality_score=quality_score,
            liveness_score=liveness_score,
            blur_variance=blur_variance,
            brightness=brightness,
            face_area_ratio=face_area_ratio,
            eye_count=eye_count,
            capture_width=client_metadata.capture_width if client_metadata else None,
            capture_height=client_metadata.capture_height if client_metadata else None,
            client_face_count=client_metadata.client_face_count if client_metadata else None,
            client_blur_score=client_metadata.client_blur_score if client_metadata else None,
            client_brightness=client_metadata.client_brightness if client_metadata else None,
            client_face_bbox=client_metadata.face_bbox if client_metadata else None,
            success=success,
            failure_reason=failure_reason,
        )
        self.db.add(attempt)
        await self.db.flush()

    def _extract_face_sample(self, file_bytes: bytes, *, enforce_liveness: bool) -> FaceFeatureSample:
        if self._analysis_app is None:
            raise ValidationError("Face model is not initialized")

        image = self._load_image(file_bytes)
        rgb = np.asarray(image)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        faces = self._analysis_app.get(bgr)
        detected_face_count = len(faces)
        if not faces:
            raise ValidationError("No face detected in the image")

        face = self._select_primary_face(faces)
        bbox = getattr(face, "bbox", None)
        embedding = getattr(face, "embedding", None)
        kps = getattr(face, "kps", None)

        if bbox is None or embedding is None:
            raise ValidationError("Face model did not return a usable embedding")

        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(gray.shape[1], x2)
        y2 = min(gray.shape[0], y2)

        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        image_area = float(gray.shape[0] * gray.shape[1])
        face_area_ratio = (width * height) / image_area
        if face_area_ratio < settings.face_login_min_face_area_ratio:
            raise ValidationError("Face is too small in the image")

        face_roi = gray[y1:y2, x1:x2]
        blur_variance = float(cv2.Laplacian(face_roi, cv2.CV_64F).var())
        brightness = float(face_roi.mean())
        eye_count = 1 if kps is not None and len(kps) >= 2 else 0

        quality_score = self._normalize_quality(
            blur_variance=blur_variance,
            brightness=brightness,
            face_area_ratio=face_area_ratio,
            eye_count=eye_count,
        )

        if enforce_liveness:
            liveness_score = self._calculate_liveness_score(
                blur_variance=blur_variance,
                brightness=brightness,
                eye_count=eye_count,
            )
            if blur_variance < settings.face_login_hard_min_blur_variance:
                raise ValidationError("Image is too blurry for face authentication")
            if (
                brightness < settings.face_login_hard_min_brightness
                or brightness > settings.face_login_hard_max_brightness
            ):
                raise ValidationError("Image lighting is unsuitable for face authentication")
            if eye_count < settings.face_login_min_eye_count:
                raise ValidationError("Anti-spoof check failed: eyes not detected clearly")
            if quality_score < settings.face_login_min_quality_score:
                raise ValidationError("Image quality is too low for face authentication")
        else:
            liveness_score = None

        descriptor = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(descriptor)
        if norm == 0:
            raise ValidationError("Unable to extract stable face embedding")
        descriptor = descriptor / norm

        return FaceFeatureSample(
            descriptor=descriptor,
            quality_score=quality_score,
            liveness_score=liveness_score,
            blur_variance=blur_variance,
            brightness=brightness,
            face_area_ratio=face_area_ratio,
            eye_count=eye_count,
            detected_face_count=detected_face_count,
        )

    def _load_image(self, file_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(BytesIO(file_bytes))
            return ImageOps.exif_transpose(image).convert("RGB")
        except Exception as exc:
            raise ValidationError(f"Invalid image file: {exc}") from exc

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            return 0.0
        return float(np.dot(a, b))

    def _select_primary_face(self, faces: list[object]) -> object:
        faces_with_area: list[tuple[object, float]] = []
        for face in faces:
            bbox = getattr(face, "bbox", None)
            if bbox is None:
                continue
            x1, y1, x2, y2 = bbox
            area = max(1.0, float((x2 - x1) * (y2 - y1)))
            faces_with_area.append((face, area))

        if not faces_with_area:
            raise ValidationError("No face detected in the image")

        faces_with_area.sort(key=lambda item: item[1], reverse=True)
        primary_face, primary_area = faces_with_area[0]
        if len(faces_with_area) > 1:
            secondary_area = faces_with_area[1][1]
            if (secondary_area / primary_area) >= settings.face_login_secondary_face_max_ratio:
                raise ValidationError("Exactly one face must be visible in the image")
        return primary_face

    def _effective_match_threshold(self, *, quality_score: float, liveness_score: float | None) -> float:
        effective = settings.face_match_threshold
        quality_penalty = max(0.0, 0.65 - quality_score) / 0.65
        effective += min(settings.face_match_max_quality_penalty, quality_penalty * settings.face_match_max_quality_penalty)
        if liveness_score is not None:
            liveness_penalty = max(0.0, 0.70 - liveness_score) / 0.70
            effective += min(
                settings.face_match_max_liveness_penalty,
                liveness_penalty * settings.face_match_max_liveness_penalty,
            )
        return round(min(0.99, effective), 4)

    def _calculate_liveness_score(self, *, blur_variance: float, brightness: float, eye_count: int) -> float:
        blur_component = min(1.0, blur_variance / max(settings.face_login_min_blur_variance * 2, 1.0))
        brightness_mid = (settings.face_login_min_brightness + settings.face_login_max_brightness) / 2
        brightness_span = max((settings.face_login_max_brightness - settings.face_login_min_brightness) / 2, 1.0)
        brightness_component = max(0.0, 1.0 - abs(brightness - brightness_mid) / brightness_span)
        eye_component = min(1.0, eye_count / max(settings.face_login_min_eye_count, 1))
        return round((blur_component * 0.45) + (brightness_component * 0.25) + (eye_component * 0.30), 4)

    def _normalize_quality(
        self, *, blur_variance: float, brightness: float, face_area_ratio: float, eye_count: int
    ) -> float:
        blur_component = min(1.0, blur_variance / 300.0)
        brightness_component = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
        face_area_component = min(1.0, face_area_ratio / 0.18)
        eye_component = min(1.0, eye_count / 2.0)
        return round((blur_component * 0.35) + (brightness_component * 0.25) + (face_area_component * 0.25) + (eye_component * 0.15), 4)
