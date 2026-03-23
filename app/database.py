import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine with proper configuration for Railway
engine = create_async_engine(
    settings.database_url_async,
    echo=settings.sqlalchemy_echo,
    # Use NullPool for Railway to avoid connection issues
    poolclass=NullPool if "railway" in settings.database_url_async.lower() else None,
    # Connection pool settings for production
    pool_size=5 if "railway" not in settings.database_url_async.lower() else None,
    max_overflow=10 if "railway" not in settings.database_url_async.lower() else None,
    pool_timeout=30,
    pool_recycle=3600,  # Recycle connections every hour
    # Ensure connections are properly closed
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass
