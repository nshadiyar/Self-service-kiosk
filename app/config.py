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
