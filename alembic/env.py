import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from app.config import settings
from app.database import Base
from app.models import (
    User,
    Facility,
    Wallet,
    Category,
    Product,
    Order,
    OrderItem,
    WalletTransaction,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_sync_url() -> str:
    """Get sync PostgreSQL URL from env (Railway) or settings. Normalizes postgres:// -> postgresql://."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PRIVATE_URL")
    if not url:
        url = settings.database_url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[11:]
    if "+asyncpg" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


sync_url = _get_sync_url()
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = sync_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
