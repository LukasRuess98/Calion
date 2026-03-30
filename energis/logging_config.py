"""
Centralized logging configuration for EnerGIS.

Usage:
    from energis.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("User-facing message")
    logger.debug("Technical detail")
"""

import io
import logging
import sys
from typing import Optional


# Module-level cache for loggers
_loggers = {}


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    include_timestamp: bool = True,
) -> None:
    """
    Configure root logger for EnerGIS.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string (optional)
        include_timestamp: Whether to include timestamp in logs
    """
    if format_string is None:
        if include_timestamp:
            format_string = '[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
        else:
            format_string = '%(name)s - %(levelname)s - %(message)s'

    # Use a UTF-8 stream handler so German/emoji characters display correctly
    # on Windows consoles that default to cp1252.
    if hasattr(sys.stdout, 'buffer'):
        utf8_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    else:
        utf8_stream = sys.stdout

    handler = logging.StreamHandler(utf8_stream)
    handler.setFormatter(logging.Formatter(format_string, datefmt='%Y-%m-%d %H:%M:%S'))

    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers added by basicConfig to avoid duplicates
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)

    # Set energis logger to configured level
    energis_logger = logging.getLogger('energis')
    energis_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger for the given module.

    Args:
        name: Module name (use __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)

    return _loggers[name]


def set_level(level: int) -> None:
    """
    Change logging level for all EnerGIS loggers.

    Args:
        level: New logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        >>> import logging
        >>> from energis.logging_config import set_level
        >>> set_level(logging.DEBUG)  # Show all debug messages
    """
    energis_logger = logging.getLogger('energis')
    energis_logger.setLevel(level)

    # Update all existing child loggers
    for logger in _loggers.values():
        logger.setLevel(level)


# Initialize with default configuration on import
setup_logging()
