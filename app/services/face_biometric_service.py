import json
from dataclasses import dataclass
from io import BytesIO
from uuid import UUID

import cv2
import numpy as np
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


@dataclass
class FaceFeatureSample:
    descriptor: np.ndarray
    quality_score: float
    liveness_score: float | None


class FaceBiometricService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self._eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

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
            provider_version="2",
            quality_score=sample.quality_score,
            is_active=True,
        )
        self.db.add(biometric)
        await self.db.flush()
        await self.db.refresh(biometric)
        return biometric

    async def authenticate(self, *, file_bytes: bytes, facility_id: UUID | None) -> tuple[User, float]:
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
                liveness_score=sample.liveness_score,
                success=False,
                failure_reason="No enrolled face biometrics found",
            )
            raise AuthenticationError("No enrolled face biometrics found")

        best_match: FaceBiometric | None = None
        best_score = 0.0
        for biometric in biometrics:
            descriptor = np.asarray(json.loads(biometric.face_signature), dtype=np.float32)
            score = self._cosine_similarity(sample.descriptor, descriptor)
            if score > best_score:
                best_score = score
                best_match = biometric

        if not best_match or best_score < settings.face_match_threshold:
            await self._log_attempt(
                user_id=None,
                facility_id=facility_id,
                score=best_score,
                liveness_score=sample.liveness_score,
                success=False,
                failure_reason="Face match threshold not reached",
            )
            raise AuthenticationError("Face authentication failed")

        await self._log_attempt(
            user_id=best_match.user_id,
            facility_id=facility_id,
            score=best_score,
            liveness_score=sample.liveness_score,
            success=True,
            failure_reason=None,
        )
        return best_match.user, best_score

    async def _log_attempt(
        self,
        *,
        user_id: UUID | None,
        facility_id: UUID | None,
        score: float | None,
        liveness_score: float | None,
        success: bool,
        failure_reason: str | None,
    ) -> None:
        attempt = FaceAuthAttempt(
            user_id=user_id,
            facility_id=facility_id,
            provider=settings.face_provider_name,
            match_score=score,
            threshold=settings.face_match_threshold,
            liveness_score=liveness_score,
            success=success,
            failure_reason=failure_reason,
        )
        self.db.add(attempt)
        await self.db.flush()

    def _extract_face_sample(self, file_bytes: bytes, *, enforce_liveness: bool) -> FaceFeatureSample:
        image_bgr = self._load_image(file_bytes)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        if len(faces) != 1:
            raise ValidationError("Exactly one face must be visible in the image")

        x, y, w, h = faces[0]
        image_area = float(gray.shape[0] * gray.shape[1])
        face_area_ratio = (w * h) / image_area
        if face_area_ratio < settings.face_login_min_face_area_ratio:
            raise ValidationError("Face is too small in the image")

        face_roi = gray[y : y + h, x : x + w]
        blur_variance = float(cv2.Laplacian(face_roi, cv2.CV_64F).var())
        brightness = float(face_roi.mean())
        eyes = self._eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=4, minSize=(18, 18))
        eye_count = len(eyes)

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
            if blur_variance < settings.face_login_min_blur_variance:
                raise ValidationError("Image is too blurry for face authentication")
            if brightness < settings.face_login_min_brightness or brightness > settings.face_login_max_brightness:
                raise ValidationError("Image lighting is unsuitable for face authentication")
            if eye_count < settings.face_login_min_eye_count:
                raise ValidationError("Anti-spoof check failed: eyes not detected clearly")
        else:
            liveness_score = None

        descriptor = self._extract_hog_descriptor(face_roi)
        return FaceFeatureSample(
            descriptor=descriptor,
            quality_score=quality_score,
            liveness_score=liveness_score,
        )

    def _load_image(self, file_bytes: bytes) -> np.ndarray:
        try:
            image = Image.open(BytesIO(file_bytes))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except Exception as exc:
            raise ValidationError(f"Invalid image file: {exc}") from exc

        rgb = np.asarray(image)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def _extract_hog_descriptor(self, face_roi: np.ndarray) -> np.ndarray:
        normalized = cv2.resize(face_roi, (128, 128), interpolation=cv2.INTER_AREA)
        hog = cv2.HOGDescriptor(
            _winSize=(128, 128),
            _blockSize=(32, 32),
            _blockStride=(16, 16),
            _cellSize=(16, 16),
            _nbins=9,
        )
        descriptor = hog.compute(normalized).flatten().astype(np.float32)
        norm = np.linalg.norm(descriptor)
        if norm == 0:
            raise ValidationError("Unable to extract stable face descriptor")
        return descriptor / norm

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            return 0.0
        return float(np.dot(a, b))

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
