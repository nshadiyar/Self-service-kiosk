"""
Application lifespan: async migrations, async scheduler, non-blocking startup.

- Миграции: asyncio.create_subprocess_exec + asyncio.wait_for (таймаут) — не блокируют event loop
- Scheduler: AsyncIOScheduler, все задачи async — не блокирует startup
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.database import engine, AsyncSessionLocal
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None
_migrations_task: asyncio.Task | None = None
MIGRATIONS_TIMEOUT = 120


async def run_migrations_background() -> None:
    """
    Запуск alembic upgrade head через asyncio.subprocess с таймаутом.
    Полностью асинхронно, не блокирует event loop.
    """
    global _migrations_task
    logger.info("Starting database migrations in background...")
    try:
        proc = await asyncio.create_subprocess_exec(
            "alembic", "upgrade", "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=MIGRATIONS_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"Migrations timeout ({MIGRATIONS_TIMEOUT}s)")
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode() if stderr else f"Exit code {proc.returncode}")
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

    port = os.environ.get("PORT", "8000")
    logger.info("Application started successfully — listening on 0.0.0.0:%s", port)

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
