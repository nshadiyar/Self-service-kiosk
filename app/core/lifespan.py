import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.database import engine, AsyncSessionLocal
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


async def reset_monthly_spending():
    """Reset monthly spending for all wallets on the 1st of each month."""
    try:
        async with AsyncSessionLocal() as db:
            wallet_service = WalletService(db)
            await wallet_service.reset_monthly_spending()
            logger.info("Monthly spending reset completed")
    except Exception as e:
        logger.error("Monthly spending reset failed: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start scheduler on startup, clean up on shutdown."""
    global scheduler
    logger.info("Starting application")

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
    logger.info("Scheduler started")

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    await engine.dispose()
    logger.info("Application shutdown complete")
