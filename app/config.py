from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Bromart Kiosk API"
    app_version: str = "1.0.0"

    # Logging
    log_level: str = "INFO"

    # Debug (set True to show exception details in 500 responses)
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bromart_db"
    sqlalchemy_echo: bool = False

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


settings = Settings()
