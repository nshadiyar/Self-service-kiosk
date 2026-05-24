import os
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Bromart Kiosk API"
    app_version: str = "1.0.0"
    # Порт из PORT (Railway), fallback 8000 для локальной разработки
    port: int = 8000

    # Logging
    log_level: str = "INFO"

    # Debug (set True to show exception details in 500 responses)
    debug: bool = False

    # Database - from DATABASE_URL or DATABASE_PRIVATE_URL (Railway); localhost default for local dev only
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bromart_db"
    sqlalchemy_echo: bool = False

    @model_validator(mode="before")
    @classmethod
    def env_database_url(cls, data: dict) -> dict:
        """Prefer DATABASE_URL or DATABASE_PRIVATE_URL from env (Railway)."""
        url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PRIVATE_URL")
        if url:
            data["database_url"] = url
        return data

    @property
    def database_url_normalized(self) -> str:
        """Normalize postgres:// to postgresql:// for SQLAlchemy (Railway uses postgres://)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[11:]
        return url

    @property
    def database_url_async(self) -> str:
        """URL for async SQLAlchemy (postgresql+asyncpg)."""
        url = self.database_url_normalized
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def database_url_sync(self) -> str:
        """URL for sync SQLAlchemy (Alembic, psycopg2)."""
        url = self.database_url_normalized
        if "+asyncpg" in url:
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url

    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # CORS
    allowed_origins: list[str] = ["*"]

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # MinIO / S3
    minio_browser_redirect_url: str | None = None
    minio_private_endpoint: str | None = None
    minio_private_host: str | None = None
    minio_private_port: int | None = None
    minio_public_endpoint: str | None = None
    minio_public_host: str | None = None
    minio_public_port: int | None = None
    minio_root_user: str | None = None
    minio_root_password: str | None = None
    minio_bucket_name: str = "inmate-photos"
    face_provider_name: str = "insightface_arcface_v1"
    face_model_name: str = "buffalo_l"
    face_match_threshold: float = 0.70
    face_login_min_blur_variance: float = 35.0
    face_login_min_brightness: float = 45.0
    face_login_max_brightness: float = 210.0
    face_login_min_face_area_ratio: float = 0.03
    face_login_min_eye_count: int = 1
    face_login_hard_min_blur_variance: float = 12.0
    face_login_hard_min_brightness: float = 18.0
    face_login_hard_max_brightness: float = 245.0
    face_login_min_quality_score: float = 0.18
    face_match_min_gap: float = 0.04
    face_match_gap_bypass_score: float = 0.82
    face_match_max_quality_penalty: float = 0.10
    face_match_max_liveness_penalty: float = 0.08
    face_login_secondary_face_max_ratio: float = 0.75

    # Feedback / Gmail SMTP
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    feedback_recipient_email: str | None = None
    feedback_subject_prefix: str = "Жалоба/Предложение"

    @property
    def s3_endpoint(self) -> str | None:
        """
        Use the Railway private endpoint only when actually running on Railway.
        For local Docker and host-based development, use the public endpoint.
        """
        in_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
        if in_railway and self.minio_private_endpoint:
            return self.minio_private_endpoint
        return self.minio_public_endpoint or self.minio_private_endpoint

    @property
    def s3_access_key(self) -> str | None:
        return self.minio_root_user

    @property
    def s3_secret_key(self) -> str | None:
        return self.minio_root_password

    @property
    def s3_secure(self) -> bool:
        endpoint = self.s3_endpoint or ""
        return endpoint.startswith("https://")

    @property
    def s3_client_endpoint(self) -> str | None:
        """Return MinIO-compatible endpoint in host[:port] format without scheme."""
        endpoint = self.s3_endpoint
        if not endpoint:
            return None
        parsed = urlparse(endpoint)
        if parsed.netloc:
            return parsed.netloc
        return endpoint.replace("http://", "").replace("https://", "")


settings = Settings()
