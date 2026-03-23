import time
from fastapi import FastAPI

from app.config import settings
from app.core.logging_config import setup_logging
from app.core.lifespan import lifespan
from app.core.middleware import register_middleware
from app.core.exception_handlers import register_exception_handlers
from app.api.v1.router import router as api_v1_router

# Setup logging before creating the app
setup_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Self-service kiosk ordering system for inmates in Kazakhstan prisons",
    lifespan=lifespan,
)

register_middleware(app)
register_exception_handlers(app)
app.include_router(api_v1_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring"""
    import time
    from app.database import AsyncSessionLocal
    
    start_time = time.time()
    
    try:
        # Test database connectivity
        async with AsyncSessionLocal() as db:
            await db.execute("SELECT 1")
        
        db_status = "healthy"
        db_response_time = round((time.time() - start_time) * 1000, 2)
        
    except Exception as e:
        db_status = "unhealthy"
        db_response_time = None
        
    # Check scheduler status
    from app.core.lifespan import scheduler
    scheduler_status = "running" if scheduler and scheduler.running else "stopped"
    
    response = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": settings.app_version,
        "timestamp": time.time(),
        "services": {
            "database": {
                "status": db_status,
                "response_time_ms": db_response_time
            },
            "scheduler": {
                "status": scheduler_status,
                "jobs_count": len(scheduler.get_jobs()) if scheduler else 0
            }
        }
    }
    
    return response


@app.get("/")
async def root():
    """Root endpoint with basic API information"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/ping")
async def ping():
    """Simple ping endpoint for basic connectivity checks"""
    return {"ping": "pong", "timestamp": time.time()}
