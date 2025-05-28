"""
Logging utilities for Playbooks debugging.

This module provides logging functionality following the debugpy pattern.
"""

import logging
import os
import sys
from typing import Optional, Set

# Log levels
LEVELS = ["debug", "info", "warning", "error", "critical"]

# Global log directory
log_dir: Optional[str] = None


# Stderr logging configuration
class StderrLogger:
    def __init__(self):
        self.levels: Set[str] = set()


stderr = StderrLogger()


def to_file(prefix: str = "playbooks"):
    """Set up file logging with the given prefix."""
    if log_dir is None:
        return

    log_file = os.path.join(log_dir, f"{prefix}.log")

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
        ],
    )


def describe_environment(message: str):
    """Log environment information."""
    logger = logging.getLogger(__name__)
    logger.info(message)
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")


def debug(message: str, *args, **kwargs):
    """Log a debug message."""
    logger = logging.getLogger(__name__)
    logger.debug(message, *args, **kwargs)
    if "debug" in stderr.levels:
        print(f"DEBUG: {message % args if args else message}", file=sys.stderr)


def info(message: str, *args, **kwargs):
    """Log an info message."""
    logger = logging.getLogger(__name__)
    logger.info(message, *args, **kwargs)
    if "info" in stderr.levels:
        print(f"INFO: {message % args if args else message}", file=sys.stderr)


def warning(message: str, *args, **kwargs):
    """Log a warning message."""
    logger = logging.getLogger(__name__)
    logger.warning(message, *args, **kwargs)
    if "warning" in stderr.levels:
        print(f"WARNING: {message % args if args else message}", file=sys.stderr)


def error(message: str, *args, **kwargs):
    """Log an error message."""
    logger = logging.getLogger(__name__)
    logger.error(message, *args, **kwargs)
    if "error" in stderr.levels:
        print(f"ERROR: {message % args if args else message}", file=sys.stderr)


def critical(message: str, *args, **kwargs):
    """Log a critical message."""
    logger = logging.getLogger(__name__)
    logger.critical(message, *args, **kwargs)
    if "critical" in stderr.levels:
        print(f"CRITICAL: {message % args if args else message}", file=sys.stderr)


def reraise_exception(message: str, *args, level: str = "error", **kwargs):
    """Log an exception and re-raise it."""
    logger = logging.getLogger(__name__)
    getattr(logger, level)(message, *args, **kwargs, exc_info=True)
    raise


def swallow_exception(message: str, *args, level: str = "error", **kwargs):
    """Log an exception without re-raising it."""
    logger = logging.getLogger(__name__)
    getattr(logger, level)(message, *args, **kwargs, exc_info=True)
