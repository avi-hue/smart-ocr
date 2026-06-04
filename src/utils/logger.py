"""
logger.py – Shared logger for the Smart-OCR project.

Usage:
    from src.utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Processing invoice: {}", filename)
"""

import sys
from loguru import logger
from src.utils.config import LOG_LEVEL, LOG_DIR

# Remove default handler
logger.remove()

# ── Console handler (coloured, human-readable) ────────────────────────────────
logger.add(
    sys.stderr,
    level=LOG_LEVEL,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    ),
    colorize=True,
)

# ── File handler (rotating, keeps last 7 days) ────────────────────────────────
logger.add(
    LOG_DIR / "smart_ocr_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="00:00",        # new file every midnight
    retention="7 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
)


def get_logger(name: str):
    """Return a logger bound to the given module name."""
    return logger.bind(name=name)
