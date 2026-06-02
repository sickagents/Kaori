"""Structured logging for LP agent."""

import logging
import sys
from datetime import datetime


def setup_logger(name: str = "lp_agent", level: int = logging.INFO) -> logging.Logger:
    """Set up structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Global logger instance
log = setup_logger()
