import os
from datetime import datetime
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler  # Keep for set_console_level type check

# Custom TRACE level (more verbose than DEBUG)
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def trace(self, message, *args, **kwargs):
    """Log at TRACE level."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


# Add trace method to Logger class
logging.Logger.trace = trace

# Log directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Formatters
SIMPLE_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Global config
_configured = False


def _cleanup_old_logs(max_files: int = 5):
    """Keep only the most recent log files."""
    log_files = sorted(LOG_DIR.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
    for old_file in log_files[max_files:]:
        old_file.unlink()


def _configure_root_logger():
    """Configure the root logger once."""
    global _configured
    if _configured:
        return
    
    root = logging.getLogger()
    root.setLevel(TRACE)  # Capture all levels
    
    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)  # Console shows INFO+
    console.setFormatter(logging.Formatter(SIMPLE_FORMAT, DATE_FORMAT))
    root.addHandler(console)
    
    # File handler - new file per run with datetime name
    log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"
    file_handler = logging.FileHandler(
        LOG_DIR / log_filename,
        encoding="utf-8"
    )
    file_handler.setLevel(TRACE)  # File captures everything
    file_handler.setFormatter(logging.Formatter(SIMPLE_FORMAT, DATE_FORMAT))
    root.addHandler(file_handler)
    
    # Cleanup old log files (keep max 5)
    _cleanup_old_logs(max_files=5)
    
    # Silence noisy library logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.
    
    Usage:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        
        logger.trace("Very detailed debug info")
        logger.debug("Debug info")
        logger.info("General info")
        logger.warning("Warning message")
        logger.error("Error occurred")
    """
    _configure_root_logger()
    return logging.getLogger(name)


def set_console_level(level: int):
    """Change console output level at runtime."""
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
            handler.setLevel(level)


# Convenience exports
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
