"""
NotesOS - Shared logging configuration.

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)

    logger.info("Job started", extra={"job_id": job_id, "topic_id": topic_id})
    logger.error("Job failed", exc_info=True, extra={"job_id": job_id})
"""

import logging
import os
import sys


def _configure_root() -> None:
    """Configure the root logger once at import time."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric = getattr(logging, log_level, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(numeric)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_configure_root()


def get_logger(name: str) -> logging.Logger:
    """Return a named logger inheriting the root configuration."""
    return logging.getLogger(name)
