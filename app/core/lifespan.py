"""
Application lifespan: async scheduler and non-blocking startup.

- Scheduler: AsyncIOScheduler, все задачи async — не блокирует startup
- Миграции выполняются вне приложения, через deploy pipeline
"""
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
    Lifespan: мгновенный startup, scheduler не блокирует event loop.
    """
    global scheduler

    port = os.environ.get("PORT", "8000")
    logger.info("Starting application — PORT=%s (from env)", port)

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

    logger.info("Application started successfully — listening on 0.0.0.0:%s", port)

    yield

    # Shutdown: останавливаем scheduler
    logger.info("Shutting down application")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    await engine.dispose()
    logger.info("Application shutdown complete")
