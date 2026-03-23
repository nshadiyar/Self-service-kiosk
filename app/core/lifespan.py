import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.config import settings
from app.database import engine, AsyncSessionLocal
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

# Глобальный scheduler для использования в lifespan
scheduler: AsyncIOScheduler | None = None


async def reset_monthly_spending():
    """Reset monthly spending for all wallets on the 1st of each month"""
    logger.info("Starting monthly spending reset task")
    try:
        async with AsyncSessionLocal() as db:
            wallet_service = WalletService(db)
            await wallet_service.reset_monthly_spending()
            logger.info("Monthly spending reset completed successfully")
    except Exception as e:
        logger.error(f"Monthly spending reset failed: {e}", exc_info=True)


async def health_check_task():
    """Periodic health check task to ensure database connectivity"""
    try:
        async with AsyncSessionLocal() as db:
            # Simple query to check DB connectivity
            await db.execute("SELECT 1")
            logger.debug("Health check passed - database is accessible")
    except Exception as e:
        logger.warning(f"Health check failed: {e}")


async def start_scheduler():
    """Initialize and start the AsyncIOScheduler"""
    global scheduler
    
    try:
        # Create scheduler with proper event loop
        scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                'coalesce': False,
                'max_instances': 1,
                'misfire_grace_time': 30
            }
        )
        
        # Add monthly reset job (1st day of each month at 00:00 UTC)
        scheduler.add_job(
            reset_monthly_spending,
            CronTrigger(day=1, hour=0, minute=0, timezone="UTC"),
            id="reset_monthly_spending",
            name="Monthly Spending Reset",
            replace_existing=True,
        )
        
        # Add health check job (every 5 minutes)
        scheduler.add_job(
            health_check_task,
            CronTrigger(minute="*/5"),
            id="health_check",
            name="Database Health Check",
            replace_existing=True,
        )
        
        # Start scheduler
        scheduler.start()
        logger.info("AsyncIOScheduler started successfully with jobs:")
        for job in scheduler.get_jobs():
            logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {job.next_run_time}")
            
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        raise


async def stop_scheduler():
    """Stop the scheduler gracefully"""
    global scheduler
    
    if scheduler and scheduler.running:
        try:
            logger.info("Stopping scheduler...")
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)
    else:
        logger.info("Scheduler was not running")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with proper async handling."""
    logger.info("🚀 Starting Bromart Kiosk API")
    
    startup_tasks = []
    
    try:
        # Start scheduler in background task to avoid blocking
        startup_tasks.append(asyncio.create_task(start_scheduler()))
        
        # Wait for all startup tasks with timeout
        await asyncio.wait_for(
            asyncio.gather(*startup_tasks, return_exceptions=True), 
            timeout=10.0
        )
        
        logger.info("✅ Application startup complete")
        
        # Application is running
        yield
        
    except asyncio.TimeoutError:
        logger.error("❌ Startup timeout - some services may not be ready")
        yield  # Still allow app to start
        
    except Exception as e:
        logger.error(f"❌ Startup error: {e}", exc_info=True)
        yield  # Still allow app to start
        
    finally:
        # Shutdown sequence
        logger.info("🔄 Shutting down Bromart Kiosk API")
        
        shutdown_tasks = []
        
        # Stop scheduler
        shutdown_tasks.append(asyncio.create_task(stop_scheduler()))
        
        # Dispose database engine
        if engine:
            shutdown_tasks.append(asyncio.create_task(engine.dispose()))
        
        try:
            # Wait for shutdown tasks with timeout
            await asyncio.wait_for(
                asyncio.gather(*shutdown_tasks, return_exceptions=True),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("⚠️ Shutdown timeout - some resources may not be cleaned up properly")
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}", exc_info=True)
        
        logger.info("✅ Application shutdown complete")
