"""
core/logging.py

Configures structured logging.
Uses `structlog` if available, with automatic fallback to standard library `logging`.
Supports "json" and "console" formatting.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def configure_logging(
    level: str = "INFO",
    fmt: Literal["json", "console"] = "json",
) -> None:
    """
    Set up structured logging.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        fmt:   Output format – "json" for production, "console" for development.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if HAS_STRUCTLOG:
        shared_processors: list = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
        ]

        renderer = (
            structlog.processors.JSONRenderer()
            if fmt == "json"
            else structlog.dev.ConsoleRenderer(colors=True)
        )

        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    else:
        # Standard library logging formatter fallback
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        formatter = logging.Formatter(log_format)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress verbose third-party logs
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
