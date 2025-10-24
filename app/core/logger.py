import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"
LOG_FORMAT = "%(levelname)s | %(asctime)s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if the logger is reused
    if not logger.handlers:
        # --- File handler (UTF-8 safe) ---
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        file_handler.setLevel(logging.INFO)

        # --- Console handler (force UTF‑8 output on all OS) ---
        try:
            # Reopen standard output stream in UTF‑8 mode
            console_stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        except Exception:
            # Fallback if running in an environment where fileno() is not allowed
            console_stream = sys.stdout

        console_handler = logging.StreamHandler(console_stream)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        console_handler.setLevel(logging.INFO)

        # Attach both handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger