"""Logging configuration."""
import logging
from pathlib import Path
from src.app.config import get_settings

def setup_logging() -> logging.Logger:
    settings = get_settings()
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("sj_home_agent")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(str(settings.log_path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

def get_logger(name: str = "sj_home_agent") -> logging.Logger:
    return logging.getLogger(name)
