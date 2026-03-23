"""Centralized logging configuration."""
import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """Configure logging for the application. Call once at startup."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"),
    )
    root.setLevel(log_level)
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for name in ("apscheduler", "apscheduler.scheduler", "tzlocal", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("app").setLevel(log_level)
