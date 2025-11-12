"""
Logging Configuration Module

Provides centralized logging setup with consistent formatting
including INFO, WARNING, ERROR labels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    console: bool = True
) -> logging.Logger:
    """
    Setup logger with consistent formatting.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: logging.INFO)
        log_file: Optional file path for log output
        console: Whether to output to console (default: True)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter with timestamp, level, and message
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one with default settings.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    # If logger has no handlers, set up default configuration
    if not logger.handlers:
        return setup_logger(name)

    return logger
