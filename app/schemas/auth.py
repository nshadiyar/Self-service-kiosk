from pydantic import BaseModel
from uuid import UUID

from app.core.enums import UserRole


class LoginRequest(BaseModel):
    """Login by email or IIN (12 digits)."""

    login: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_role: UserRole


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str


class FaceLoginResponse(Token):
    matched_user_id: UUID
    match_score: float
    provider: str


class FaceClientMetadata(BaseModel):
    capture_width: int | None = None
    capture_height: int | None = None
    client_face_count: int | None = None
    client_blur_score: float | None = None
    client_brightness: float | None = None
    face_bbox: str | None = None
