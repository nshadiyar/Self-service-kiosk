import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.config import settings
from app.database import engine, AsyncSessionLocal
from app.services.wallet_service import WalletService

_log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(level=_log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def reset_monthly_spending():
    """Reset monthly spending for all wallets on the 1st of each month"""
    try:
        async with AsyncSessionLocal() as db:
            wallet_service = WalletService(db)
            await wallet_service.reset_monthly_spending()
            logger.info("Monthly spending reset completed")
    except Exception as e:
        logger.warning("Monthly spending reset failed (table may not exist): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Bromart Kiosk API")
    scheduler.add_job(
        reset_monthly_spending,
        CronTrigger(day=1, hour=0, minute=0),
        id="reset_monthly_spending",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")
    yield
    scheduler.shutdown()
    await engine.dispose()
    logger.info("Bromart Kiosk API shutdown complete")
