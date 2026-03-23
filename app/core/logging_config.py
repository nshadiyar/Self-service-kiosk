"""Centralized logging configuration for the application."""
import logging
import sys
from typing import Dict, Any

from app.config import settings


def setup_logging() -> None:
    """Configure logging for the entire application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configure root logger
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logger_config: Dict[str, Any] = {
        "apscheduler": logging.WARNING,
        "apscheduler.scheduler": logging.WARNING,
        "tzlocal": logging.WARNING,
        "uvicorn": logging.INFO,
        "uvicorn.access": logging.WARNING,  # Disable access logs (we handle them via middleware)
        "uvicorn.error": logging.INFO,
        "sqlalchemy.engine": logging.WARNING,
        "alembic": logging.INFO,
    }
    
    for logger_name, level in logger_config.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Application loggers
    logging.getLogger("app").setLevel(log_level)