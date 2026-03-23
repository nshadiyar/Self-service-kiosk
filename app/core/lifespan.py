"""
Application lifespan: background migrations, async scheduler, graceful shutdown.

Все операции при startup выполняются неблокирующе:
- Миграции запускаются в фоне (asyncio.to_thread) — приложение стартует мгновенно
- Scheduler (AsyncIOScheduler) работает в том же event loop, не блокирует его
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.database import engine, AsyncSessionLocal
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None
_migrations_task: asyncio.Task | None = None


def _run_migrations_sync() -> None:
    """
    Синхронный запуск alembic upgrade head.
    Вызывается из asyncio.to_thread — не блокирует event loop.
    """
    root = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


async def run_migrations_background() -> None:
    """
    Запуск миграций в фоновом потоке.
    Не блокирует startup — приложение сразу отвечает на / и /health.
    """
    global _migrations_task
    logger.info("Starting database migrations in background...")
    try:
        await asyncio.to_thread(_run_migrations_sync)
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error("Database migrations failed: %s", e, exc_info=True)
    finally:
        _migrations_task = None


async def reset_monthly_spending() -> None:
    """Сброс месячных трат по кошелькам — 1-го числа каждого месяца."""
    try:
        async with AsyncSessionLocal() as db:
            wallet_service = WalletService(db)
            await wallet_service.reset_monthly_spending()
            logger.info("Monthly spending reset completed")
    except Exception as e:
        logger.error("Monthly spending reset failed: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan: мгновенный startup, миграции в фоне, scheduler не блокирует event loop.
    """
    global scheduler, _migrations_task

    logger.info("Starting application")

    # 1. Scheduler — AsyncIOScheduler использует текущий event loop, не блокирует
    scheduler = AsyncIOScheduler(
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    )
    scheduler.add_job(
        reset_monthly_spending,
        CronTrigger(day=1, hour=0, minute=0),
        id="reset_monthly_spending",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (async, non-blocking)")

    # 2. Миграции в фоне — приложение сразу готово к приёму запросов
    _migrations_task = asyncio.create_task(run_migrations_background())

    yield

    # Shutdown: отменяем миграции если ещё выполняются, останавливаем scheduler
    logger.info("Shutting down application")
    if _migrations_task and not _migrations_task.done():
        _migrations_task.cancel()
        try:
            await _migrations_task
        except asyncio.CancelledError:
            logger.warning("Migrations task was cancelled during shutdown")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    await engine.dispose()
    logger.info("Application shutdown complete")
